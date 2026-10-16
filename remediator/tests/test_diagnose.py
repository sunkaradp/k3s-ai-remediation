from app import diagnose
from app.models import Alert, Context


def ctx(alertname: str) -> Context:
    return Context(alert=Alert(status="firing", labels={"alertname": alertname}))


def test_rules_oomkilled():
    d = diagnose.by_rules(ctx("PodOOMKilled"))
    assert d.runbook == "increase_memory"
    assert d.source == "rules"


def test_rules_unknown_alert():
    assert diagnose.by_rules(ctx("SomethingNew")).runbook == "none"


def test_parse_valid_llm_answer():
    d = diagnose.parse('{"runbook": "restart_pod", "reason": "stuck", "confidence": 0.7}')
    assert d is not None and d.runbook == "restart_pod" and d.source == "llm"


def test_parse_rejects_runbook_outside_allowlist():
    assert diagnose.parse('{"runbook": "delete_namespace", "reason": "x", "confidence": 1}') is None


def test_parse_rejects_bad_json():
    assert diagnose.parse("sure! I think you should restart it") is None


def test_parse_rejects_confidence_out_of_range():
    assert diagnose.parse('{"runbook": "restart_pod", "reason": "x", "confidence": 7}') is None


def test_falls_back_to_rules_when_llm_down(monkeypatch):
    def boom(_):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(diagnose, "LLM_ENABLED", True)
    monkeypatch.setattr(diagnose, "by_llm", boom)
    assert diagnose.diagnose(ctx("PodOOMKilled")).source == "rules"


def test_prompt_contains_allowlist_and_logs():
    c = ctx("PodOOMKilled")
    c.logs = "java.lang.OutOfMemoryError"
    p = diagnose.build_prompt(c)
    assert "increase_memory" in p and "OutOfMemoryError" in p
