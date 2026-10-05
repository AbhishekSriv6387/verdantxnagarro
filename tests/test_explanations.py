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


def test_narration_runs_after_commit_and_does_not_lock_store(settings):
    from concurrent.futures import ThreadPoolExecutor
    from app.service import SchedulerService
    from app.store.sqlite import Store
    store = Store(":memory:")
    class CheckingExplainer:
        def explain(self, decision):
            assert not store.db.in_transaction
            with ThreadPoolExecutor(max_workers=1) as pool:
                def read():
                    with store.lock:
                        return len(store.logs())
                assert pool.submit(read).result(timeout=2) == 25
            decision["outcome"] = "CORRUPTED"
            return "Optional prose"
    service = SchedulerService(settings, store, explainer=CheckingExplainer())
    service.cycle()
    assert store.db.execute("SELECT COUNT(*) FROM explanations").fetchone()[0] == 25
    assert all(j.decision["outcome"] != "CORRUPTED" for j in store.jobs())
    assert all("llm_explanation" not in j.decision for j in store.jobs())
    assert service.cycle()["processed"] == 0
    store.db.close()
