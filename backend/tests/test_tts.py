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
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "")
    monkeypatch.setattr(config, "TENCENT_ASR_REGION", "ap-shanghai")
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


def test_tts_tencent_returns_mp3_with_compatible_speed(client, monkeypatch):
    import app.api.tts as tts_api

    monkeypatch.setattr(config, "TTS_PROVIDER", "tencent")
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "fake-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "fake-key")
    calls = []

    def fake_synthesize(text, voice_type, speed):
        calls.append((text, voice_type, speed))
        return b"ID3fake-mp3"

    monkeypatch.setattr(tts_api.tts_tencent, "synthesize", fake_synthesize)
    resp = client.post(
        "/api/tts",
        json={"text": "你好", "speed": 0.9},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/mpeg")
    assert resp.content == b"ID3fake-mp3"
    assert calls == [("你好", 101001, 0.9)]


def test_tts_tencent_missing_credentials_503(client, monkeypatch):
    monkeypatch.setattr(config, "TTS_PROVIDER", "tencent")
    resp = client.post("/api/tts", json={"text": "你好"}, headers=_auth())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "语音合成服务未配置"


def test_tts_tencent_failure_is_generic_and_hides_source_text(client, monkeypatch, caplog):
    import app.api.tts as tts_api
    from app.services.tts_tencent import TtsError

    source_text = "这句回复不能出现在失败响应或日志里"
    monkeypatch.setattr(config, "TTS_PROVIDER", "tencent")
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "fake-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "fake-key")

    def fail_synthesize(*_args, **_kwargs):
        raise TtsError("FailedOperation")

    monkeypatch.setattr(tts_api.tts_tencent, "synthesize", fail_synthesize)
    resp = client.post("/api/tts", json={"text": source_text}, headers=_auth())
    assert resp.status_code == 502
    assert resp.json()["detail"] == "语音暂时播不出来，先看文字吧"
    assert source_text not in resp.text
    assert source_text not in caplog.text


def test_tts_tencent_not_open_returns_503(client, monkeypatch):
    import app.api.tts as tts_api
    from app.services.tts_tencent import TtsError

    monkeypatch.setattr(config, "TTS_PROVIDER", "tencent")
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "fake-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "fake-key")
    monkeypatch.setattr(
        tts_api.tts_tencent,
        "synthesize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            TtsError("UnsupportedOperation.ServerNotOpen")
        ),
    )
    resp = client.post("/api/tts", json={"text": "你好"}, headers=_auth())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "语音合成服务未配置或未开通"


def test_tts_speed_out_of_range_422(client):
    resp = client.post(
        "/api/tts",
        json={"text": "你好", "speed": 1.2},
        headers=_auth(),
    )
    assert resp.status_code == 422
