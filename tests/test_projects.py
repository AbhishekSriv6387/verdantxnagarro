from datetime import timedelta
import pytest
from conftest import NOW


def test_project_filters_rollups_and_approver_audit(client):
    data = {"name":"Project report", "owner":"Test", "project":"commerce", "team":"Finance",
            "est_duration_min":60, "power_kw":5, "criticality":"business_critical",
            "earliest_start":(NOW+timedelta(hours=6)).isoformat(), "sla_deadline":(NOW+timedelta(hours=23)).isoformat()}
    assert client.post("/api/jobs", json={**data, "project":" "}).status_code == 422
    job = client.post("/api/jobs", json=data).json()
    assert client.get("/api/state?project=commerce").json()["jobs"][0]["id"] == job["id"]
    client.post("/api/agent/cycle")
    url = f"/api/approvals/{job['id']}"
    # Reviewer identity is now supplied by the authenticated session, not this field.
    assert client.post(url, json={"action":"approve", "comment":"Reviewed", "approver_name":" "}).status_code == 422
    assert client.post(url, json={"action":"approve", "comment":"Reviewed", "approver_name":" Alice "}).status_code == 200
    logs = client.get("/api/logs?project=commerce&actor=human").json()
    assert len(logs) == 1 and logs[0]["approver_name"] == "Platform administrator"
    assert logs[0]["team"] == "Finance"
    filtered = client.get("/api/report?project=commerce").json()
    assert filtered["total_jobs"] == filtered["included_jobs"] == 1
    assert filtered["rows"][0]["project"] == "commerce"
    total = client.get("/api/report").json()
    assert sum(p["avoided_g"] for p in total["projects"]) == pytest.approx(total["avoided_g"])
    assert client.get("/api/report/export?project=commerce").json() == filtered
    csv = client.get("/api/report/export?project=commerce&format=csv").text
    assert "Finance" in csv and "Warehouse refresh" not in csv
    assert len(client.get("/api/jobs?project=commerce").json()) == 1
    assert client.get("/api/report?project=missing").json()["total_jobs"] == 0
    assert len(client.get("/api/analysis/flexibility?project=commerce").json()["points"][0]["rows"]) == 1


def test_cross_project_dependency_guard_survives_filter(client):
    data = {"name":"Cross-project parent", "owner":"Test", "project":"parent-project", "team":"Data",
            "est_duration_min":60, "power_kw":5,
            "earliest_start":(NOW+timedelta(hours=6)).isoformat(), "sla_deadline":(NOW+timedelta(hours=23)).isoformat()}
    parent = client.post("/api/jobs", json=data).json()
    child = client.post("/api/jobs", json={**data, "name":"Child", "project":"child-project", "depends_on":[parent["id"]]}).json()
    client.get("/api/state?project=parent-project")
    client.post("/api/agent/cycle")
    result = client.get("/api/jobs?project=parent-project").json()[0]
    assert result["status"] == "needs_approval"
    assert client.get("/api/jobs?project=child-project").json()[0]["status"] == "pending"
    assert client.get("/api/analysis/flexibility?project=parent-project").json()["points"][0]["included_jobs"] == 0
