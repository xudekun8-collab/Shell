"""腾讯云一句话识别接口测试：全程不真调云。"""
import pytest
import httpx
from fastapi.testclient import TestClient

from app import config
from app.services.asr import AsrError
from app.services.token import create_token

SECRET = "asr-test-secret"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "")
    from app.main import app

    return TestClient(app)


def _elder_headers():
    return {"Authorization": "Bearer " + create_token("demo_user_1", "elder", SECRET)}


def test_asr_no_token_401(client):
    resp = client.post("/api/asr", json={"audio_base64": "AAAA"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "未登录"


def test_asr_no_key_503(client):
    resp = client.post("/api/asr", json={"audio_base64": "AAAA"}, headers=_elder_headers())
    assert resp.status_code == 503
    assert resp.json()["detail"] == "语音识别服务未配置"


def test_asr_empty_audio_422(client):
    resp = client.post("/api/asr", json={"audio_base64": ""}, headers=_elder_headers())
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(e.get("loc") and "audio_base64" in e["loc"] for e in detail)


def test_asr_mock_recognize_200(client, monkeypatch):
    import app.api.asr as asr_api_mod

    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "fake-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "fake-key")
    monkeypatch.setattr(asr_api_mod, "recognize", lambda audio, fmt: "今天天气不错")
    resp = client.post("/api/asr", json={"audio_base64": "AAAA"}, headers=_elder_headers())
    assert resp.status_code == 200
    assert resp.json()["text"] == "今天天气不错"


def test_asr_family_403(client):
    headers = {"Authorization": "Bearer " + create_token("fam_1", "family", SECRET)}
    resp = client.post("/api/asr", json={"audio_base64": "AAAA"}, headers=headers)
    assert resp.status_code == 403


def test_asr_invalid_base64_400(client, monkeypatch):
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "fake-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "fake-key")
    resp = client.post("/api/asr", json={"audio_base64": "not base64 !!!"}, headers=_elder_headers())
    assert resp.status_code == 400
    assert resp.json()["detail"] == "音频数据不合法"


def test_asr_cloud_error_502_hides_code(client, monkeypatch):
    import app.api.asr as asr_api_mod

    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "fake-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "fake-key")

    def fail_recognize(audio, fmt):
        raise AsrError("FailedOperation.NoSpeech")

    monkeypatch.setattr(asr_api_mod, "recognize", fail_recognize)
    resp = client.post("/api/asr", json={"audio_base64": "AAAA"}, headers=_elder_headers())
    assert resp.status_code == 502
    assert resp.json()["detail"] == "这会儿没听清，您再说一遍"
    assert "FailedOperation" not in resp.text


def test_asr_network_error_becomes_asr_error(monkeypatch):
    import app.services.asr as asr_service

    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "fake-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "fake-key")

    def fail_client(*args, **kwargs):
        raise httpx.ConnectError("blocked")

    monkeypatch.setattr(asr_service.httpx, "Client", fail_client)
    with pytest.raises(AsrError) as exc_info:
        asr_service.recognize(b"audio")
    assert exc_info.value.code == "RequestFailed"
