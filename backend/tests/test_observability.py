"""请求日志与健康检查可观测性测试。"""
import logging
import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app import config


def _client(monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "engine", create_engine("sqlite://"))
    return TestClient(main_mod.app), main_mod


def test_health_reports_observability_without_secrets(monkeypatch):
    client, main_mod = _client(monkeypatch)
    monkeypatch.setattr(main_mod, "_PROCESS_STARTED_AT", time.time() - 10)
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "secret-id")
    monkeypatch.setattr(config, "TTS_API_KEY", "tts-key")
    body = client.get("/api/health").json()
    assert set(body) == {"status", "db", "uptime_sec", "asr_configured", "tts_configured"}
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["uptime_sec"] >= 9
    assert body["asr_configured"] is True
    assert body["tts_configured"] is True
    assert "secret-id" not in str(body)
    assert "tts-key" not in str(body)


def test_health_unconfigured_flags_are_false(monkeypatch):
    client, _ = _client(monkeypatch)
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "id-only")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "")
    monkeypatch.setattr(config, "TTS_API_KEY", "")
    monkeypatch.setattr(config, "TTS_PROVIDER", "")
    body = client.get("/api/health").json()
    assert body["asr_configured"] is False
    assert body["tts_configured"] is False
    response = client.get("/api/health", headers={"Origin": "https://example.invalid"})
    assert "access-control-allow-origin" not in response.headers


def test_health_detects_tencent_tts_from_cloud_credentials(monkeypatch):
    client, _ = _client(monkeypatch)
    monkeypatch.setattr(config, "TTS_API_KEY", "")
    monkeypatch.setattr(config, "TTS_PROVIDER", "tencent")
    monkeypatch.setattr(config, "TENCENT_SECRET_ID", "secret-id")
    monkeypatch.setattr(config, "TENCENT_SECRET_KEY", "secret-key")
    body = client.get("/api/health").json()
    assert body["tts_configured"] is True


def test_health_degraded_keeps_200(monkeypatch):
    import app.main as main_mod

    class BadEngine:
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(main_mod, "engine", BadEngine())
    body = TestClient(main_mod.app).get("/api/health").json()
    assert body["status"] == "ok"
    assert body["db"] == "degraded"


def test_request_logs_without_query_or_headers(monkeypatch, caplog):
    client, _ = _client(monkeypatch)
    caplog.set_level(logging.INFO, logger="elder_care")
    client.get(
        "/api/health?secret_query=do-not-log",
        headers={"Authorization": "Bearer do-not-log", "Cookie": "do-not-log"},
    )
    client.get("/api/records?token=do-not-log")
    messages = [record.getMessage() for record in caplog.records if record.name == "elder_care"]
    health_log = next(message for message in messages if "GET /api/health 200" in message)
    auth_log = next(message for message in messages if "GET /api/records 401" in message)
    combined = health_log + auth_log
    assert "secret_query" not in combined
    assert "do-not-log" not in combined
    assert "Bearer" not in combined
    assert "Cookie" not in combined
    assert "ms" in health_log


def test_slow_request_logs_warning(monkeypatch, caplog):
    client, main_mod = _client(monkeypatch)
    monkeypatch.setattr(main_mod, "SLOW_REQUEST_MS", 1.0)
    clock = {"value": 10.0}

    def perf_counter():
        value = clock["value"]
        clock["value"] += 0.002
        return value

    monkeypatch.setattr(main_mod.time, "perf_counter", perf_counter)
    caplog.set_level(logging.INFO, logger="elder_care")
    assert client.get("/api/health").status_code == 200
    slow = [
        record
        for record in caplog.records
        if record.name == "elder_care" and record.getMessage().startswith("SLOW ")
    ]
    assert slow
    assert slow[-1].levelno == logging.WARNING
    assert "GET /api/health 200" in slow[-1].getMessage()


def test_logging_failure_does_not_break_request(monkeypatch):
    client, main_mod = _client(monkeypatch)

    def fail_log(*args, **kwargs):
        raise RuntimeError("logger broken")

    monkeypatch.setattr(main_mod.logger, "info", fail_log)
    assert client.get("/api/health").status_code == 200
