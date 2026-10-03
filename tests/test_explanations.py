from dataclasses import replace

import httpx

from app.engine.explanations import OpenAIExplainer
from app.engine.scheduler import decide
from conftest import NOW, make_curve


def test_explanation_disabled_and_fallback(settings, job, monkeypatch):
    decision = decide(job, [job], NOW, make_curve(), settings)
    assert OpenAIExplainer(settings).explain(decision) is None
    enabled = replace(settings, enable_llm=True, openai_key="test")
    def failure(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx.Client, "post", failure)
    assert OpenAIExplainer(enabled).explain(decision) is None
    assert decision["outcome"] == "AUTO_RESCHEDULED"


def test_explanation_sends_only_decision_summary(settings, job, monkeypatch):
    decision = decide(job, [job], NOW, make_curve(), settings)
    def success(self, url, **kwargs):
        assert url == "https://api.openai.com/v1/responses"
        assert kwargs["json"]["store"] is False
        assert job.name not in kwargs["json"]["input"]
        assert kwargs["headers"]["Authorization"] == "Bearer test"
        return httpx.Response(200, request=httpx.Request("POST", url), json={"output": [{"content": [{"type": "output_text", "text": "SIMULATED savings explain the proposed move."}]}]})
    monkeypatch.setattr(httpx.Client, "post", success)
    assert "SIMULATED" in OpenAIExplainer(replace(settings, enable_llm=True, openai_key="test")).explain(decision)
