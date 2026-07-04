"""共用 fixtures — API 測試用 TestClient(暫存 DB 隔離)。"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web.app as webapp  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """每個測試一顆全新暫存 DB;startup 事件 init 的是 monkeypatch 後的路徑,
    絕不觸碰 data/animal_an.db 正式資料庫。"""
    monkeypatch.setattr(webapp, "DB_PATH", tmp_path / "web_test.db")
    with TestClient(webapp.app, raise_server_exceptions=False) as c:
        yield c
