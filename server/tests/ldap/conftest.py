from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch, tmp_path):
    """Изолирует тесты от LDAP_*-переменных и `.env` разработчика."""
    for name in list(os.environ):
        if name.startswith("LDAP_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
