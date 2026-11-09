from types import SimpleNamespace

from ldap3 import NONE, Server

from app.integrations.ldap.client import _Ldap3Connection, _receive_timeout
from app.integrations.ldap.config import LdapSettings


def test_receive_timeout_is_ceiled_to_int():
    assert _receive_timeout(5.0) == 5
    assert _receive_timeout(5.5) == 6
    assert _receive_timeout(0.5) == 1


def test_connection_gets_integer_receive_timeout(monkeypatch):
    """ldap3 на POSIX пакует receive_timeout в struct timeval — float падает."""
    captured = {}

    class FakeConnection:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            self.closed = False
            self.server = SimpleNamespace(current_address=None)

        def open(self):
            pass

        def start_tls(self):
            return True

        def unbind(self):
            pass

    monkeypatch.setattr("app.integrations.ldap.client.Connection", FakeConnection)

    settings = LdapSettings(enabled=False, timeout=2.5)
    _Ldap3Connection(Server("127.0.0.1", port=389, get_info=NONE), settings)

    assert captured["receive_timeout"] == 3
    assert isinstance(captured["receive_timeout"], int)
