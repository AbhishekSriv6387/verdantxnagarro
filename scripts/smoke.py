"""Exercise a RUNNING local demo. Resets demo jobs; preserves all decision history."""
import json
import os
import sys
from pathlib import Path

import httpx


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    from dotenv import load_dotenv
    load_dotenv()
    username, password = os.getenv("SMOKE_USERNAME", "admin"), os.getenv("SMOKE_PASSWORD")
    if not password:
        raise SystemExit("Set SMOKE_PASSWORD for an authorized account; this script resets its selected environment.")
    environment_id = os.getenv("SMOKE_ENVIRONMENT_ID", "env-default")
    with httpx.Client(base_url=base, timeout=60, headers={"X-Environment-ID": environment_id}) as client:
        client.post("/api/auth/login", json={"username": username, "password": password}).raise_for_status()
        def get(path: str):
            response = client.get(path)
            response.raise_for_status()
            return response

        def post(path: str, body: dict | None = None):
            response = client.post(path, json=body or {})
            response.raise_for_status()
            return response.json()

        for path in ("/", "/static/app.js", "/static/styles.css", "/docs", "/openapi.json", "/api/health"):
            get(path)
        post("/api/demo/reset")
        cycle = post("/api/agent/cycle")
        assert cycle["processed"] == 25
        assert post("/api/agent/cycle")["processed"] == 0
        first_report = get("/api/report").json()
        assert first_report["avoided_g"] > 0
        get("/api/jobs/demo-01/curve")
        proposals = get("/api/approvals").json()
        post(f"/api/approvals/{proposals[0]['id']}", {"action": "approve", "approver_name": "Test reviewer", "comment": "Smoke test: reviewed SLA and business window"})
        post(f"/api/approvals/{proposals[1]['id']}", {"action": "reject", "approver_name": "Test reviewer", "comment": "Smoke test: owner retains control"})
        get("/api/logs?actor=human")
        for fmt in ("csv", "json"):
            get(f"/api/report/export?format={fmt}")
        replay = post("/api/demo/replay")
        assert replay["total_jobs"] == 175 and replay["source"] == "SIMULATED"
        get("/api/report/export?format=csv&scope=replay")
        state = get("/api/state").json()
        post("/api/jobs", {"name": "Smoke-test ETL", "owner": "Verification", "zone": "DE", "type": "etl",
                           "est_duration_min": 60, "power_kw": 2, "earliest_start": state["clock"],
                           "sla_deadline": "2026-10-10T00:00:00Z"})
        post("/api/clock/advance", {"minutes": 60})
        # Leave a clean, already-evaluated showcase; previous evidence is still queryable.
        post("/api/demo/reset")
        post("/api/agent/cycle")
        post("/api/demo/replay")
        evidence = {"verification": "Real HTTP requests against running uvicorn server", "source": first_report["source"],
                    "seed": 42, "daily": {k: first_report[k] for k in ("included_jobs", "excluded_jobs", "avoided_g", "reduction_pct", "projected_weekly_g")},
                    "replay": {k: replay[k] for k in ("total_jobs", "included_jobs", "avoided_g", "reduction_pct", "seed", "source")},
                    "pending_approvals_after_first_cycle": len(proposals),
                    "verified": ["offline assets", "OpenAPI", "health", "cycle", "idempotence", "curve", "approval", "rejection", "audit", "CSV", "JSON", "replay", "add job", "advance", "reset"]}
        output = Path(__file__).resolve().parents[1] / "docs" / "demo-evidence.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
