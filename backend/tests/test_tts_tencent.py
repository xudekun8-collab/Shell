"""腾讯云 TTS 服务测试：不调用真实云接口。"""
import base64
import json

import pytest

from app import config
from app.services import tts_tencent


class _Response:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self._body


@pytest.fixture(autouse=True)
def fake_config(monkeypatch):
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "fake-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "fake-key")
    monkeypatch.setattr(config, "TENCENT_ASR_REGION", "ap-shanghai")
    monkeypatch.setattr(config, "TTS_VOICE", "")
    tts_tencent._CACHE.clear()


def test_tencent_tts_builds_request_and_truncates_text(monkeypatch):
    captured = {}
    audio = b"fake-mp3"

    def fake_urlopen(req, data=None, timeout=None):
        assert data is None
        captured["request"] = req
        captured["timeout"] = timeout
        return _Response({"Response": {"Audio": base64.b64encode(audio).decode("ascii")}})

    monkeypatch.setattr(tts_tencent.urlrequest, "urlopen", fake_urlopen)
    result = tts_tencent.synthesize("字" * 130, voice_type=101002, speed=0.9)

    payload = json.loads(captured["request"].data.decode("utf-8"))
    headers = {key.lower(): value for key, value in captured["request"].header_items()}
    assert result == audio
    assert len(payload["Text"]) == 120
    assert payload["VoiceType"] == 101002
    assert payload["Codec"] == "mp3"
    assert payload["SampleRate"] == 16000
    assert payload["Speed"] == 0.9
    assert len(payload["SessionId"]) == 32
    assert headers["x-tc-action"] == "TextToVoice"
    assert headers["x-tc-version"] == "2019-08-23"
    assert headers["x-tc-region"] == "ap-shanghai"
    assert headers["authorization"].startswith("TC3-HMAC-SHA256 Credential=fake-id/")
    assert "/tts/tc3_request" in headers["authorization"]


def test_tencent_tts_caches_same_text_voice_and_speed(monkeypatch):
    calls = []

    def fake_urlopen(req, data=None, timeout=None):
        assert data is None
        calls.append(req)
        return _Response({"Response": {"Audio": base64.b64encode(b"audio").decode("ascii")}})

    monkeypatch.setattr(tts_tencent.urlrequest, "urlopen", fake_urlopen)
    first = tts_tencent.synthesize("你好", voice_type=101001, speed=1.0)
    second = tts_tencent.synthesize("你好", voice_type=101001, speed=1.0)

    assert first == second == b"audio"
    assert len(calls) == 1


def test_tencent_tts_error_log_does_not_include_source_text(monkeypatch, caplog):
    source_text = "这是一段绝不能出现在日志里的测试原文"

    def fake_urlopen(req, data=None, timeout=None):
        assert data is None
        return _Response(
            {
                "Response": {
                    "Error": {
                        "Code": "FailedOperation",
                        "Message": "synthetic failure",
                    }
                }
            }
        )

    monkeypatch.setattr(tts_tencent.urlrequest, "urlopen", fake_urlopen)
    with pytest.raises(tts_tencent.TtsError) as exc_info:
        tts_tencent.synthesize(source_text)

    assert exc_info.value.code == "FailedOperation"
    assert source_text not in caplog.text
