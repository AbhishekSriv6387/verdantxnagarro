"""Optional narration plug-in: receives an immutable decision copy, returns text only."""
import json
from typing import Protocol

import httpx

from app.config import Settings


class Explainer(Protocol):
    def explain(self, decision: dict) -> str | None: ...


class OpenAIExplainer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def explain(self, decision: dict) -> str | None:
        if not self.settings.enable_llm or not self.settings.openai_key:
            return None
        summary = {key: decision[key] for key in ("outcome", "rule_ids", "carbon_before_g", "carbon_after_g", "source", "explanation")}
        try:
            with httpx.Client(timeout=8) as client:
                response = client.post("https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {self.settings.openai_key}"},
                    json={"model": self.settings.openai_model, "max_output_tokens": 180, "store": False,
                          "instructions": "Explain this already-final scheduling decision in two plain sentences. Preserve source labels and uncertainty. Do not propose actions or change any values or rules.",
                          "input": json.dumps(summary)})
                response.raise_for_status()
                text = " ".join(content.get("text", "") for output in response.json().get("output", [])
                                for content in output.get("content", []) if content.get("type") == "output_text")
                return text[:1500] or None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None
