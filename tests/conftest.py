"""Shared fixtures for Aquatek integration tests."""
import sys
from unittest.mock import MagicMock

import pytest
import pytest_socket

# pytest-homeassistant-custom-component calls disable_socket(allow_unix_socket=True)
# in its pytest_runtest_setup hook. On Linux/Mac asyncio uses AF_UNIX internally
# so that's fine. On Windows, ProactorEventLoop falls back to TCP socketpair()
# (AF_INET) which is still blocked. We hook into pytest_fixture_setup to
# re-enable sockets at the last possible moment before event_loop is created.
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_fixture_setup(fixturedef, request):
    if fixturedef.argname == "event_loop":
        pytest_socket.enable_socket()
    yield

# Tell pytest-homeassistant-custom-component to load integrations from
# the local custom_components/ directory.
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


# Stub native C extension packages before integration code imports them.
# awscrt / awsiot require compiled binaries that won't be present in a test venv.
for _mod in ("awscrt", "awscrt.mqtt", "awsiot", "awsiot.mqtt_connection_builder"):
    sys.modules.setdefault(_mod, MagicMock())

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

DEVICE_ID = "12345678901234567"

FAKE_CERTS = {
    "cert_id": "abcdef1234567890abcdef1234567890abcdef12",
    "cert_pem": "-----BEGIN CERTIFICATE-----\nFAKEDATA\n-----END CERTIFICATE-----\n",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nFAKEDATA\n-----END RSA PRIVATE KEY-----\n",
}
