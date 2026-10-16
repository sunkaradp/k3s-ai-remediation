from app.policy import Tier, decide


def test_observe_mode_never_acts():
    assert decide("restart_pod", 0.99, Tier.OBSERVE) == Tier.OBSERVE


def test_low_risk_high_confidence_runs_auto():
    assert decide("restart_pod", 0.9, Tier.AUTO) == Tier.AUTO


def test_medium_risk_needs_approval_even_in_auto():
    assert decide("rollback_deployment", 0.99, Tier.AUTO) == Tier.APPROVAL


def test_low_confidence_only_observes():
    assert decide("restart_pod", 0.3, Tier.AUTO) == Tier.OBSERVE


def test_unknown_runbook_only_observes():
    assert decide("rm -rf /", 1.0, Tier.AUTO) == Tier.OBSERVE


def test_none_runbook_only_observes():
    assert decide("none", 1.0, Tier.AUTO) == Tier.OBSERVE
