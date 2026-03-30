"""Tests for mqtt_client.py — topic construction and MAC normalisation."""
from unittest.mock import MagicMock

from custom_components.aquatek.mqtt_client import AquatekMQTTClient, _normalise_mac


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
