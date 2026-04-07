"""Tests for mqtt_client.py — topic construction and MAC normalisation."""
from unittest.mock import MagicMock

from custom_components.dontek_aquatek.mqtt_client import (
    AquatekLocalMQTTClient,
    AquatekMQTTClient,
    ConnectionState,
    _normalise_mac,
)


# ---------------------------------------------------------------------------
# _normalise_mac
# ---------------------------------------------------------------------------


def test_normalise_mac_strips_colons():
    assert _normalise_mac("AA:BB:CC:DD:EE:FF") == "aabbccddeeff"


def test_normalise_mac_strips_dashes():
    assert _normalise_mac("AA-BB-CC-DD-EE-FF") == "aabbccddeeff"


def test_normalise_mac_passthrough_clean():
    assert _normalise_mac("aabbccddeeff") == "aabbccddeeff"


def test_normalise_mac_lowercases():
    assert _normalise_mac("AABBCCDDEEFF") == "aabbccddeeff"


# ---------------------------------------------------------------------------
# AquatekMQTTClient — topic construction
# ---------------------------------------------------------------------------


def _make_client(mac: str) -> AquatekMQTTClient:
    return AquatekMQTTClient(
        mac=mac,
        cert_pem="pem",
        private_key="key",
        message_callback=MagicMock(),
        state_callback=MagicMock(),
    )


def test_topic_status_uses_dontek_prefix():
    client = _make_client("aa:bb:cc:dd:ee:ff")
    assert client._topic_status == "dontekaabbccddeeff/status/psw"


def test_topic_cmd_uses_dontek_prefix():
    client = _make_client("aa:bb:cc:dd:ee:ff")
    assert client._topic_cmd == "dontekaabbccddeeff/cmd/psw"


def test_topic_shadow_uppercased():
    client = _make_client("aa:bb:cc:dd:ee:ff")
    assert client._topic_shadow == "$aws/things/AABBCCDDEEFF_VERSION/shadow/get/+"


def test_topics_accept_colon_mac():
    client = _make_client("AA:BB:CC:DD:EE:FF")
    assert client._topic_status == "dontekaabbccddeeff/status/psw"
    assert client._topic_cmd == "dontekaabbccddeeff/cmd/psw"


def test_topics_accept_clean_mac():
    client = _make_client("aabbccddeeff")
    assert client._topic_status == "dontekaabbccddeeff/status/psw"


def test_client_id_uses_normalised_mac():
    client = _make_client("AA:BB:CC:DD:EE:FF")
    assert client._client_id.startswith("aquatek-aabbccddeeff-")


def test_mac_stored_normalised():
    client = _make_client("AA:BB:CC:DD:EE:FF")
    assert client._mac == "aabbccddeeff"


# ---------------------------------------------------------------------------
# ConnectionState — ONLINE removed
# ---------------------------------------------------------------------------


def test_connection_state_has_no_online():
    states = [s.name for s in ConnectionState]
    assert "ONLINE" not in states


def test_connection_state_values():
    assert ConnectionState.DISCONNECTED.value == "Disconnected"
    assert ConnectionState.CONNECTING.value == "Connecting"
    assert ConnectionState.CONNECTED.value == "Connected"


# ---------------------------------------------------------------------------
# AquatekLocalMQTTClient — construction and topic generation
# ---------------------------------------------------------------------------


def _make_local_client(mac: str) -> AquatekLocalMQTTClient:
    return AquatekLocalMQTTClient(
        mac=mac,
        host="localhost",
        port=11883,
        message_callback=MagicMock(),
        state_callback=MagicMock(),
    )


def test_local_client_topic_status():
    client = _make_local_client("aa:bb:cc:dd:ee:ff")
    assert client._topic_status == "dontekaabbccddeeff/status/psw"


def test_local_client_topic_cmd():
    client = _make_local_client("aa:bb:cc:dd:ee:ff")
    assert client._topic_cmd == "dontekaabbccddeeff/cmd/psw"


def test_local_client_mac_normalised():
    client = _make_local_client("AA:BB:CC:DD:EE:FF")
    assert client._mac == "aabbccddeeff"


def test_local_client_stores_host_and_port():
    client = _make_local_client("aabbccddeeff")
    assert client._host == "localhost"
    assert client._port == 11883


def test_local_client_id_uses_normalised_mac():
    client = _make_local_client("AA:BB:CC:DD:EE:FF")
    assert client._client_id.startswith("aquatek-aabbccddeeff-")


def test_local_client_initial_state_disconnected():
    client = _make_local_client("aabbccddeeff")
    assert client.state == ConnectionState.DISCONNECTED
