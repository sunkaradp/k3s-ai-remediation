import pytest

from app import runbooks
from app.models import Alert, Context


def ctx(
    owner_kind: str = "Deployment",
    labels: dict[str, str] | None = None,
) -> Context:
    alert_labels = {
        "alertname": "x",
        "namespace": "demo",
        "pod": "api-1",
        "container": "api",
    }
    if labels:
        alert_labels.update(labels)
    alert = Alert(status="firing", labels=alert_labels)
    return Context(alert=alert, owner_kind=owner_kind, owner_name="api")


def test_mutating_runbooks_fail_closed_without_namespace_allowlist(monkeypatch):
    monkeypatch.delenv("REMEDIATION_ALLOWED_NAMESPACES", raising=False)
    assert runbooks.restart_pod(ctx()).startswith("skipped")
    assert runbooks.rollback_deployment(ctx()).startswith("skipped")
    assert runbooks.increase_memory(ctx()).startswith("skipped")
    assert runbooks.scale_up(ctx()).startswith("skipped")


def test_mutating_runbooks_reject_non_allowlisted_namespace(monkeypatch):
    monkeypatch.setenv("REMEDIATION_ALLOWED_NAMESPACES", "staging, production")
    assert runbooks.restart_pod(ctx()).startswith("skipped")


def test_dry_run_is_default_for_allowlisted_namespace(monkeypatch):
    monkeypatch.setenv("REMEDIATION_ALLOWED_NAMESPACES", "demo")
    monkeypatch.setattr(runbooks, "DRY_RUN", True)
    assert runbooks.restart_pod(ctx()).startswith("[dry-run]")


def test_rollback_skips_non_deployment(monkeypatch):
    monkeypatch.setenv("REMEDIATION_ALLOWED_NAMESPACES", "demo")
    assert runbooks.rollback_deployment(ctx("StatefulSet")).startswith("skipped")


def test_memory_change_requires_explicit_container(monkeypatch):
    monkeypatch.setenv("REMEDIATION_ALLOWED_NAMESPACES", "demo")
    monkeypatch.setattr(runbooks, "DRY_RUN", True)
    context = ctx(labels={"container": ""})
    assert runbooks.increase_memory(context) == "skipped: alert is missing container label"


def test_unknown_runbook_does_nothing():
    assert runbooks.run("delete_everything", ctx()) == "no action"


@pytest.mark.parametrize(
    ("quantity", "expected"),
    [
        ("512Ki", 1),
        ("512Mi", 512),
        ("1Gi", 1024),
        ("2Ti", 2 * 1024 * 1024),
        ("268435456", 256),
    ],
)
def test_memory_units(quantity, expected):
    assert runbooks.to_mi(quantity) == expected


@pytest.mark.parametrize("quantity", ["", "invalid", "-1Mi", "NaN", "Infinity"])
def test_invalid_memory_quantity_is_rejected(quantity):
    with pytest.raises(ValueError, match="invalid memory quantity"):
        runbooks.to_mi(quantity)
