import time
from app.workload import generate_jobs
from conftest import NOW


def test_scale_seed_distribution_and_performance(client):
    assert generate_jobs(NOW, 500) == generate_jobs(NOW, 500)
    jobs = generate_jobs(NOW, 500)
    assert sum(j.criticality == "hard_deadline" for j in jobs) == 75
    assert sum(j.criticality == "business_critical" for j in jobs) == 50
    assert any(j.depends_on for j in jobs)
    assert client.post("/api/demo/scale", json={"n":501}).status_code == 422
    assert client.post("/api/demo/scale", json={"n":500}).json()["workload_source"] == "SIMULATED WORKLOAD"
    started = time.perf_counter()
    result = client.post("/api/agent/cycle").json()
    elapsed = time.perf_counter() - started
    print(f"500-job cycle: {elapsed:.3f}s")
    assert result["processed"] == 500
    assert elapsed < 5, f"500-job cycle took {elapsed:.3f}s"
    assert client.post("/api/agent/cycle").json()["processed"] == 0
    assert len(client.get("/api/logs").json()) == 500
    assert client.post("/api/demo/scale", json={}).json()["jobs"] == 25
    assert len(client.get("/api/logs?all_runs=true").json()) == 500
