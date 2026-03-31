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
    TOPIC_SHADOW,
    TOPIC_STATUS,
    WATCHDOG_TIMEOUT,
)

def _normalise_mac(mac: str) -> str:
    """Return lowercase no-colon MAC (e.g. 'aabbccddeeff')."""
    return mac.replace(":", "").replace("-", "").lower()

_LOGGER = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    ONLINE = "Online"  # connected + received at least one status message


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
        self._watchdog_task: asyncio.Task | None = None
        self._last_message_time: float = 0.0
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

            # Start watchdog
            if self._watchdog_task:
                self._watchdog_task.cancel()
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())

        except Exception:
            _LOGGER.exception("Failed to connect to AWS IoT MQTT")
            self._set_state(ConnectionState.DISCONNECTED)
            self._schedule_reconnect()

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

        import time  # noqa: PLC0415
        self._last_message_time = time.monotonic()

        if self._state != ConnectionState.ONLINE:
            self._set_state(ConnectionState.ONLINE)

        self._message_callback(reg, vals)

    async def disconnect(self) -> None:
        """Gracefully disconnect and cancel background tasks."""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self._watchdog_task:
            self._watchdog_task.cancel()
            self._watchdog_task = None

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
                next_delay = min(delay * 2, RECONNECT_MAX)
                self._schedule_reconnect(next_delay)

    async def _watchdog_loop(self) -> None:
        """Periodically check that status messages are still arriving.

        If no message is received within WATCHDOG_TIMEOUT seconds, treat the
        device as offline and trigger reconnect. Mirrors the app's 180-second
        timeout logic in b3/q.java case 0.
        """
        import time  # noqa: PLC0415
        while True:
            await asyncio.sleep(30)
            if self._state == ConnectionState.ONLINE:
                age = time.monotonic() - self._last_message_time
                if age > WATCHDOG_TIMEOUT:
                    _LOGGER.warning(
                        "No status message for %.0fs — marking offline", age
                    )
                    self._set_state(ConnectionState.CONNECTED)
