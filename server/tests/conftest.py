import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))


@pytest.fixture
def make_client(monkeypatch):
    """Build a TestClient with the given environment."""
    from fastapi.testclient import TestClient

    clients = []

    def make(**env):
        for k in list(os.environ):
            if k.startswith("SIGNAL_LAB_"):
                monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("SIGNAL_LAB_PLUGINS_DIR", str(ROOT / "plugins"))
        monkeypatch.setenv("SIGNAL_LAB_STATIC_DIR", str(ROOT / "nonexistent"))
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        from signal_lab.api import create_app
        from signal_lab.config import Settings

        client = TestClient(create_app(Settings()))
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for c in clients:
        c.__exit__(None, None, None)
