from fastapi.testclient import TestClient

from app import context, diagnose, main
from app.models import Context
from app.policy import Tier

client = TestClient(main.app)


def payload(alertname: str, status: str = "firing") -> dict:
    return {
        "status": status,
        "receiver": "remediator",
        "alerts": [
            {
                "status": status,
                "labels": {"alertname": alertname, "namespace": "demo", "pod": "api-123"},
                "annotations": {},
            }
        ],
    }


def no_cluster(monkeypatch, mode: Tier):
    monkeypatch.setattr(context, "collect", lambda a: Context(alert=a))
    monkeypatch.setattr(diagnose, "LLM_ENABLED", False)
    monkeypatch.setenv("REMEDIATION_MODE", mode.value)


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_observe_mode_takes_no_action(monkeypatch):
    no_cluster(monkeypatch, Tier.OBSERVE)
    r = client.post("/webhook/alertmanager", json=payload("PodOOMKilled")).json()
    assert r[0]["tier"] == "OBSERVE" and r[0]["action"] == "observed only"


def test_medium_risk_waits_for_approval(monkeypatch):
    no_cluster(monkeypatch, Tier.AUTO)
    r = client.post("/webhook/alertmanager", json=payload("PodOOMKilled")).json()
    assert r[0]["diagnosis"]["runbook"] == "increase_memory"
    assert r[0]["tier"] == "APPROVAL"


def test_resolved_alerts_are_ignored(monkeypatch):
    no_cluster(monkeypatch, Tier.AUTO)
    r = client.post("/webhook/alertmanager", json=payload("PodOOMKilled", "resolved"))
    assert r.json() == []


def test_metrics_exposed():
    assert client.get("/metrics/").status_code == 200
