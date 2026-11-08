"""require_demo_token 口令校验的单元测试（该依赖已退居次要，但仍保留）。"""
import pytest
from fastapi import HTTPException

from app.api.deps import require_demo_token


def test_no_token_set_passes(monkeypatch):
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    require_demo_token(None)


def test_token_set_without_header_rejected(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "abc123")
    with pytest.raises(HTTPException) as exc:
        require_demo_token(None)
    assert exc.value.status_code == 401


def test_token_set_with_correct_header_passes(monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "abc123")
    require_demo_token("abc123")
