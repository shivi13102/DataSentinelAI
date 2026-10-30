from types import SimpleNamespace

import requests

from src.agents import reasoning_agent


def _response(payload):
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: payload,
    )


def test_ai_health_requires_successful_inference(monkeypatch):
    calls = []

    def request(url, **kwargs):
        method = "get" if url == reasoning_agent.OLLAMA_TAGS_URL else "post"
        calls.append((method, url, kwargs["timeout"]))
        if method == "get":
            return _response({"models": [{"name": reasoning_agent.DEFAULT_MODEL}]})
        return _response({"response": "DATASENTINEL_OK", "done": True})

    monkeypatch.setattr(reasoning_agent.requests, "get", request)
    monkeypatch.setattr(reasoning_agent.requests, "post", request)

    result = reasoning_agent.check_ai_health()

    assert result["status"] == "AVAILABLE"
    assert result["ollama_reachable"] is True
    assert result["model_installed"] is True
    assert result["inference_tested"] is True
    assert result["response_time_ms"] >= 0
    assert [call[0] for call in calls] == ["get", "post"]


def test_ai_health_reports_unavailable_ollama(monkeypatch):
    def fail_connection(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("private connection details")

    monkeypatch.setattr(reasoning_agent.requests, "get", fail_connection)

    result = reasoning_agent.check_ai_health()

    assert result["status"] == "OLLAMA_UNAVAILABLE"
    assert result["ollama_reachable"] is False
    assert result["inference_tested"] is False
    assert "private connection details" not in str(result)


def test_ai_health_reports_missing_model_without_inference(monkeypatch):
    monkeypatch.setattr(
        reasoning_agent.requests,
        "get",
        lambda *_args, **_kwargs: _response({"models": [{"name": "other:latest"}]}),
    )
    inference_calls = []
    monkeypatch.setattr(
        reasoning_agent.requests,
        "post",
        lambda *args, **kwargs: inference_calls.append(args),
    )

    result = reasoning_agent.check_ai_health()

    assert result["status"] == "MODEL_NOT_INSTALLED"
    assert result["ollama_reachable"] is True
    assert result["model_installed"] is False
    assert result["inference_tested"] is False
    assert inference_calls == []


def test_ai_health_reports_failed_inference(monkeypatch):
    monkeypatch.setattr(
        reasoning_agent.requests,
        "get",
        lambda *_args, **_kwargs: _response(
            {"models": [{"name": reasoning_agent.DEFAULT_MODEL}]}
        ),
    )
    monkeypatch.setattr(
        reasoning_agent.requests,
        "post",
        lambda *_args, **_kwargs: _response({"response": "", "done": True}),
    )

    result = reasoning_agent.check_ai_health()

    assert result["status"] == "INFERENCE_FAILED"
    assert result["ollama_reachable"] is True
    assert result["model_installed"] is True
    assert result["inference_tested"] is False


def test_ai_health_reports_inference_timeout(monkeypatch):
    monkeypatch.setattr(
        reasoning_agent.requests,
        "get",
        lambda *_args, **_kwargs: _response(
            {"models": [{"name": reasoning_agent.DEFAULT_MODEL}]}
        ),
    )

    def timeout(*_args, **_kwargs):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(reasoning_agent.requests, "post", timeout)

    result = reasoning_agent.check_ai_health()

    assert result["status"] == "INFERENCE_FAILED"
    assert result["model_installed"] is True
    assert result["inference_tested"] is False
    assert "within" in result["error"]


def test_ai_health_reports_not_configured(monkeypatch):
    monkeypatch.setattr(reasoning_agent, "AI_PROVIDER", "external")

    result = reasoning_agent.check_ai_health()

    assert result["status"] == "NOT_CONFIGURED"
    assert result["inference_tested"] is False
