from app import runbooks
from app.models import Alert, Context


def ctx(owner_kind="Deployment") -> Context:
    alert = Alert(status="firing", labels={"alertname": "x", "namespace": "demo", "pod": "api-1"})
    return Context(alert=alert, owner_kind=owner_kind, owner_name="api")


def test_dry_run_is_default():
    assert runbooks.restart_pod(ctx()).startswith("[dry-run]")


def test_rollback_skips_non_deployment():
    assert runbooks.rollback_deployment(ctx("StatefulSet")).startswith("skipped")


def test_unknown_runbook_does_nothing():
    assert runbooks.run("delete_everything", ctx()) == "no action"


def test_memory_units():
    assert runbooks.to_mi("512Mi") == 512
    assert runbooks.to_mi("1Gi") == 1024
    assert runbooks.to_mi("268435456") == 256
