"""语音合成骨架接口测试。"""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.services.token import create_token

SECRET = "tts-test-secret"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "TTS_API_KEY", "")
    monkeypatch.setattr(config, "TTS_VOICE", "")
    monkeypatch.setattr(config, "TTS_PROVIDER", "")
    from app.main import app

    return TestClient(app)


def _auth():
    return {"Authorization": "Bearer " + create_token("demo_user_1", "elder", SECRET)}


def test_tts_no_token_401(client):
    resp = client.post("/api/tts", json={"text": "你好"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "未登录"


def test_tts_no_key_503(client):
    resp = client.post("/api/tts", json={"text": "你好"}, headers=_auth())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "语音合成服务未配置"


def test_tts_empty_text_422(client):
    resp = client.post("/api/tts", json={"text": ""}, headers=_auth())
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(e.get("loc") and "text" in e["loc"] for e in detail)


def test_tts_key_set_501(client, monkeypatch):
    monkeypatch.setattr(config, "TTS_API_KEY", "fake-key")
    resp = client.post("/api/tts", json={"text": "你好"}, headers=_auth())
    assert resp.status_code == 501
    assert resp.json()["detail"] == "语音合成尚未接入，见 docs/tts.md"
