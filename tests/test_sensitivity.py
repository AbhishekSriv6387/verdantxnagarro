from datetime import datetime
from app.providers.carbon import SyntheticProvider


def test_sensitivity_frozen_isolated_and_constraints(client):
    client.post("/api/agent/cycle")
    before = client.get("/api/state").json()
    logs = client.get("/api/logs").json()
    result = client.get("/api/analysis/flexibility").json()
    assert [p["flexibility_hours"] for p in result["points"]] == [1,2,4,8]
    assert result["source"] == "SIMULATED"
    assert "14:00" in result["baseline"]
    savings = [p["modeled_saving_g"] for p in result["points"]]
    assert savings == sorted(savings)
    jobs = {j["id"]: j for j in before["jobs"]}
    for point in result["points"]:
        for row in point["rows"]:
            job = jobs[row["job_id"]]
            assert datetime.fromisoformat(row["baseline_start"]) == datetime.fromisoformat(job["baseline_start"])
            if row["included"]:
                assert job["criticality"] == "flexible" and not job["depends_on"]
                assert not any(job["id"] in j["depends_on"] for j in jobs.values())
    client.app.state.service.provider = SyntheticProvider(1234)
    assert client.get("/api/analysis/flexibility").json() == result
    assert client.get("/api/state").json() == before
    assert client.get("/api/logs").json() == logs
