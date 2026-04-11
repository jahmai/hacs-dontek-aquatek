"""AWS IoT MQTT client for the Dontek Aquatek integration.

Handles connection lifecycle, message parsing, reconnection, and command publishing.

Protocol (from decompiled app b3/v.java, e3/g.java):
  - Subscribe: {MAC}/status/psw  — device pushes state as Modbus register updates
  - Publish:   {MAC}/cmd/psw     — send commands as Modbus register writes
  - Message format: {"messageId": "read"|"write", "modbusReg": N, "modbusVal": [N, ...]}

The MAC address in topics is used as-is; shadow topics use it uppercased (b3/v.java line 390).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from enum import Enum

from .const import (
    IOT_ENDPOINT,
    RECONNECT_MAX,
    RECONNECT_MIN,
    TOPIC_CMD,
    TOPIC_LOGGING,
    TOPIC_SHADOW,
    TOPIC_STATUS,
)

def _normalise_mac(mac: str) -> str:
    """Return lowercase no-colon MAC (e.g. 'aabbccddeeff')."""
    return mac.replace(":", "").replace("-", "").lower()

_LOGGER = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    CONNECTED = "Connected"


MessageCallback = Callable[[int, list[int]], None]
StateCallback = Callable[[ConnectionState], None]


class AquatekMQTTClient:
    """Manages the AWS IoT MQTT connection for a single Aquatek controller."""

    def __init__(
        self,
        mac: str,
        cert_pem: str,
        private_key: str,
        message_callback: MessageCallback,
        state_callback: StateCallback,
    ) -> None:
        mac_norm = _normalise_mac(mac)
        self._mac = mac_norm
        self._cert_pem = cert_pem
        self._private_key = private_key
        self._message_callback = message_callback
        self._state_callback = state_callback

        self._connection = None
        self._mqtt_module = None
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        self._topic_status = TOPIC_STATUS.format(mac=mac_norm)
        self._topic_cmd = TOPIC_CMD.format(mac=mac_norm)
        self._topic_shadow = TOPIC_SHADOW.format(mac_upper=mac_norm.upper())

        # Unique client ID per session — matches app behaviour (UUID per session)
        self._client_id = f"aquatek-{mac_norm}-{uuid.uuid4().hex[:8]}"

    @property
    def state(self) -> ConnectionState:
        return self._state

    def _set_state(self, state: ConnectionState) -> None:
        if state != self._state:
            self._state = state
            self._state_callback(state)

    async def connect(self) -> None:
        """Establish MQTT connection and start background tasks."""
        self._loop = asyncio.get_running_loop()
        self._set_state(ConnectionState.CONNECTING)
        await self._do_connect()
        if self._state == ConnectionState.DISCONNECTED:
            self._schedule_reconnect()

    def _build_mqtt_connection(self):
        """Build the awsiotsdk connection object (blocking — run in executor)."""
        from awscrt import mqtt as _mqtt  # noqa: PLC0415
        from awsiot import mqtt_connection_builder  # noqa: PLC0415

        self._mqtt_module = _mqtt
        return mqtt_connection_builder.mtls_from_bytes(
            endpoint=IOT_ENDPOINT,
            cert_bytes=self._cert_pem.encode(),
            pri_key_bytes=self._private_key.encode(),
            client_id=self._client_id,
            clean_session=False,
            keep_alive_secs=60,
            on_connection_interrupted=self._on_interrupted,
            on_connection_resumed=self._on_resumed,
        )

    async def _do_connect(self) -> None:
        """Build awsiotsdk connection and connect."""
        try:
            # mtls_from_bytes does blocking I/O (package metadata reads) on first
            # import — run it in a thread so the event loop stays responsive.
            self._connection = await self._loop.run_in_executor(
                None, self._build_mqtt_connection
            )
            mqtt = self._mqtt_module

            connect_future = self._connection.connect()
            await asyncio.wrap_future(connect_future)

            self._set_state(ConnectionState.CONNECTED)
            _LOGGER.info("Connected to AWS IoT MQTT for %s", self._mac)

            # Subscribe to device status topic
            subscribe_future, _ = self._connection.subscribe(
                topic=self._topic_status,
                qos=mqtt.QoS.AT_MOST_ONCE,
                callback=self._on_message_raw,
            )
            await asyncio.wrap_future(subscribe_future)

            # Subscribe to shadow topic — AWS IoT publishes the current shadow state
            # on subscribe, which may trigger the device to send a full state dump.
            # Wrapped separately so a policy denial here doesn't break status messages.
            try:
                shadow_future, _ = self._connection.subscribe(
                    topic=self._topic_shadow,
                    qos=mqtt.QoS.AT_MOST_ONCE,
                    callback=self._on_shadow_raw,
                )
                await asyncio.wrap_future(shadow_future)
                _LOGGER.debug("Subscribed to shadow topic %s", self._topic_shadow)
            except Exception:
                _LOGGER.debug("Shadow topic subscribe failed (policy may not permit it)")

            _LOGGER.debug("Subscribed to %s", self._topic_status)

            # Request full state dump — mirrors what the app sends on connect.
            # modbusReg=1 with messageId="read" triggers the device to push its
            # complete register state (the bulk key-value dump format).
            state_request = json.dumps({"messageId": "read", "modbusReg": 1, "modbusVal": [1]})
            pub_future, _ = self._connection.publish(
                topic=self._topic_cmd,
                payload=state_request,
                qos=mqtt.QoS.AT_MOST_ONCE,
            )
            await asyncio.wrap_future(pub_future)
            _LOGGER.debug("Sent state dump request")

        except Exception:
            _LOGGER.exception("Failed to connect to AWS IoT MQTT")
            self._set_state(ConnectionState.DISCONNECTED)

    def _on_interrupted(self, connection, error, **kwargs) -> None:
        _LOGGER.warning("MQTT connection interrupted: %s", error)
        self._set_state(ConnectionState.DISCONNECTED)

    def _on_resumed(self, connection, return_code, session_present, **kwargs) -> None:
        _LOGGER.info("MQTT connection resumed")
        self._set_state(ConnectionState.CONNECTED)

    def _on_message_raw(self, topic: str, payload: bytes, **kwargs) -> None:
        """Raw MQTT callback — runs on awscrt thread, schedule onto event loop."""
        assert self._loop is not None
        _LOGGER.debug("Received MQTT message on %s (%d bytes)", topic, len(payload))
        self._loop.call_soon_threadsafe(self._handle_message, payload)

    def _on_shadow_raw(self, topic: str, payload: bytes, **kwargs) -> None:
        """Shadow topic callback — ignored for now, reserved for version info."""

    def _handle_message(self, payload: bytes) -> None:
        """Parse a status message and dispatch to coordinator."""
        try:
            data = json.loads(payload)
            reg = int(data["modbusReg"])
            vals = [int(v) for v in data["modbusVal"]]
        except (json.JSONDecodeError, KeyError, ValueError):
            _LOGGER.debug("Unparseable message: %s", payload[:120])
            return

        self._message_callback(reg, vals)

    async def disconnect(self) -> None:
        """Gracefully disconnect and cancel background tasks."""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        if self._connection:
            try:
                disconnect_future = self._connection.disconnect()
                await asyncio.wrap_future(disconnect_future)
            except Exception:
                pass
            self._connection = None

        self._set_state(ConnectionState.DISCONNECTED)
        _LOGGER.debug("Disconnected from AWS IoT MQTT")

    async def publish_command(self, reg: int, values: list[int]) -> bool:
        """Publish a Modbus write command to the device."""
        if not self._connection or self._state == ConnectionState.DISCONNECTED:
            _LOGGER.warning("Cannot publish — not connected")
            return False

        payload = json.dumps({
            "messageId": "write",
            "modbusReg": reg,
            "modbusVal": values,
        })

        try:
            from awscrt import mqtt  # noqa: PLC0415
            pub_future, _ = self._connection.publish(
                topic=self._topic_cmd,
                payload=payload,
                qos=mqtt.QoS.AT_MOST_ONCE,
            )
            await asyncio.wrap_future(pub_future)
            return True
        except Exception:
            _LOGGER.exception("Failed to publish command reg=%d vals=%s", reg, values)
            return False

    def _schedule_reconnect(self, delay: float = RECONNECT_MIN) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_after(delay))

    async def _reconnect_after(self, delay: float) -> None:
        """Wait then attempt reconnection with exponential backoff."""
        await asyncio.sleep(delay)
        if self._state == ConnectionState.DISCONNECTED:
            _LOGGER.info("Attempting MQTT reconnect...")
            await self._do_connect()
            if self._state == ConnectionState.DISCONNECTED:
                # Assign directly — _schedule_reconnect's guard would block us
                # because this task is still running at this point.
                next_delay = min(delay * 2, RECONNECT_MAX)
                self._reconnect_task = asyncio.create_task(self._reconnect_after(next_delay))

    async def _poll_state(self) -> None:
        """Send a full-state-dump request to the device."""
        if not self._connection or self._state == ConnectionState.DISCONNECTED:
            return
        try:
            from awscrt import mqtt  # noqa: PLC0415
            state_request = json.dumps({"messageId": "read", "modbusReg": 1, "modbusVal": [1]})
            pub_future, _ = self._connection.publish(
                topic=self._topic_cmd,
                payload=state_request,
                qos=mqtt.QoS.AT_MOST_ONCE,
            )
            await asyncio.wrap_future(pub_future)
            _LOGGER.debug("Sent periodic state poll")
        except Exception:
            _LOGGER.debug("Periodic state poll failed")



class AquatekLocalMQTTClient:
    """Plain-TCP MQTT client for connecting to a local broker (no TLS, no AWS)."""

    def __init__(
        self,
        mac: str,
        host: str,
        port: int,
        message_callback: MessageCallback,
        state_callback: StateCallback,
    ) -> None:
        mac_norm = _normalise_mac(mac)
        self._mac = mac_norm
        self._host = host
        self._port = port
        self._message_callback = message_callback
        self._state_callback = state_callback

        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_task: asyncio.Task | None = None
        self._connect_future: asyncio.Future | None = None

        self._topic_status = TOPIC_STATUS.format(mac=mac_norm)
        self._topic_cmd = TOPIC_CMD.format(mac=mac_norm)
        self._topic_logging = TOPIC_LOGGING
        self._client_id = f"aquatek-{mac_norm}-{uuid.uuid4().hex[:8]}"

    @property
    def state(self) -> ConnectionState:
        return self._state

    def _set_state(self, state: ConnectionState) -> None:
        if state != self._state:
            self._state = state
            self._state_callback(state)

    async def connect(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._set_state(ConnectionState.CONNECTING)
        await self._do_connect()
        if self._state == ConnectionState.DISCONNECTED:
            self._schedule_reconnect()

    async def _do_connect(self) -> None:
        import paho.mqtt.client as mqtt  # noqa: PLC0415

        if self._client is not None:
            try:
                self._client.loop_stop()
            except Exception:
                pass
            self._client = None

        try:
            from paho.mqtt.client import CallbackAPIVersion  # noqa: PLC0415
            client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION1,
                client_id=self._client_id,
                clean_session=False,
            )
        except ImportError:
            # paho-mqtt < 2.0
            client = mqtt.Client(client_id=self._client_id, clean_session=False)

        client.on_connect = self._on_paho_connect
        client.on_disconnect = self._on_paho_disconnect
        client.on_message = self._on_paho_message

        # TLS without server certificate validation — the firmware requires TLS
        # but cannot validate a self-signed broker cert.
        import ssl  # noqa: PLC0415
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

        self._client = client

        connect_future: asyncio.Future = self._loop.create_future()
        self._connect_future = connect_future

        try:
            # Timeout the TCP connect — without this, an unreachable host blocks
            # a thread for the OS TCP timeout (~20 s). The abandoned thread will
            # eventually resolve harmlessly; stale paho callbacks are ignored via
            # the `client is not self._client` guard in each callback.
            await asyncio.wait_for(
                self._loop.run_in_executor(
                    None, lambda: client.connect(self._host, self._port, keepalive=60)
                ),
                timeout=10.0,
            )
            client.loop_start()
            await asyncio.wait_for(connect_future, timeout=10.0)
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timed out connecting to local MQTT broker at %s:%d", self._host, self._port
            )
            try:
                client.loop_stop()
            except Exception:
                pass
            self._set_state(ConnectionState.DISCONNECTED)
        except Exception:
            _LOGGER.exception(
                "Failed to connect to local MQTT broker at %s:%d", self._host, self._port
            )
            try:
                client.loop_stop()
            except Exception:
                pass
            self._set_state(ConnectionState.DISCONNECTED)

    def _on_paho_connect(self, client, userdata, flags, rc) -> None:
        if client is not self._client:
            return  # stale callback from a superseded connection attempt
        assert self._loop is not None
        if rc == 0:
            self._loop.call_soon_threadsafe(self._handle_connected)
        else:
            self._loop.call_soon_threadsafe(
                self._handle_connect_failed, Exception(f"MQTT connect refused: rc={rc}")
            )

    def _handle_connected(self) -> None:
        if self._connect_future and not self._connect_future.done():
            self._connect_future.set_result(True)
        self._set_state(ConnectionState.CONNECTED)
        self._client.subscribe(self._topic_status, qos=0)
        self._client.subscribe(self._topic_logging, qos=0)
        state_request = json.dumps({"messageId": "read", "modbusReg": 1, "modbusVal": [1]})
        self._client.publish(self._topic_cmd, state_request, qos=0)
        _LOGGER.info("Connected to local MQTT broker at %s:%d", self._host, self._port)

    def _handle_connect_failed(self, exc: Exception) -> None:
        if self._connect_future and not self._connect_future.done():
            self._connect_future.set_exception(exc)

    def _on_paho_disconnect(self, client, userdata, rc) -> None:
        if client is not self._client:
            return  # stale callback from a superseded connection attempt
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._handle_disconnected, rc)

    def _handle_disconnected(self, rc: int) -> None:
        if rc != 0:
            _LOGGER.warning("Local MQTT broker disconnected unexpectedly: rc=%d", rc)
        self._set_state(ConnectionState.DISCONNECTED)
        self._schedule_reconnect()

    def _on_paho_message(self, client, userdata, msg) -> None:
        if client is not self._client:
            return  # stale callback from a superseded connection attempt
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._handle_message, msg.payload)

    def _handle_message(self, payload: bytes) -> None:
        try:
            data = json.loads(payload)
            reg = int(data["modbusReg"])
            vals = [int(v) for v in data["modbusVal"]]
        except (json.JSONDecodeError, KeyError, ValueError):
            _LOGGER.debug("Unparseable message: %s", payload[:120])
            return

        self._message_callback(reg, vals)

    async def disconnect(self) -> None:
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._set_state(ConnectionState.DISCONNECTED)

    async def publish_command(self, reg: int, values: list[int]) -> bool:
        if not self._client or self._state == ConnectionState.DISCONNECTED:
            _LOGGER.warning("Cannot publish — not connected")
            return False
        payload = json.dumps({
            "messageId": "write",
            "modbusReg": reg,
            "modbusVal": values,
        })
        result = self._client.publish(self._topic_cmd, payload, qos=0)
        return result.rc == 0

    async def _poll_state(self) -> None:
        """Send a full-state-dump request to the device."""
        if not self._client or self._state == ConnectionState.DISCONNECTED:
            return
        state_request = json.dumps({"messageId": "read", "modbusReg": 1, "modbusVal": [1]})
        try:
            self._client.publish(self._topic_cmd, state_request, qos=0)
            _LOGGER.debug("Sent state poll request")
        except Exception:
            _LOGGER.debug("State poll failed")

    def _schedule_reconnect(self, delay: float = RECONNECT_MIN) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_after(delay))

    async def _reconnect_after(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if self._state == ConnectionState.DISCONNECTED:
            _LOGGER.info("Attempting local MQTT reconnect...")
            await self._do_connect()
            if self._state == ConnectionState.DISCONNECTED:
                # Assign directly — _schedule_reconnect's guard would block us
                # because this task is still running at this point.
                next_delay = min(delay * 2, RECONNECT_MAX)
                self._reconnect_task = asyncio.create_task(self._reconnect_after(next_delay))
