"""Decides how much freedom the remediator has for a given fix.

OBSERVE  - log the diagnosis only
APPROVAL - ask a human before acting
AUTO     - apply the runbook right away
"""

import os
from enum import StrEnum


class Tier(StrEnum):
    OBSERVE = "OBSERVE"
    APPROVAL = "APPROVAL"
    AUTO = "AUTO"


# Risk per runbook. Only "low" risk fixes can ever run without a human.
RISK = {
    "none": "none",
    "restart_pod": "low",
    "scale_up": "low",
    "increase_memory": "medium",
    "rollback_deployment": "medium",
}

AUTO_MIN_CONFIDENCE = float(os.getenv("AUTO_MIN_CONFIDENCE", "0.8"))
ACT_MIN_CONFIDENCE = float(os.getenv("ACT_MIN_CONFIDENCE", "0.5"))


def global_mode() -> Tier:
    """Cluster-wide ceiling. Default is OBSERVE so a fresh install never touches anything."""
    return Tier(os.getenv("REMEDIATION_MODE", "OBSERVE").upper())


def decide(runbook: str, confidence: float, mode: Tier | None = None) -> Tier:
    mode = mode or global_mode()
    risk = RISK.get(runbook)

    if risk in (None, "none") or mode == Tier.OBSERVE:
        return Tier.OBSERVE
    if confidence < ACT_MIN_CONFIDENCE:
        return Tier.OBSERVE
    if mode == Tier.AUTO and risk == "low" and confidence >= AUTO_MIN_CONFIDENCE:
        return Tier.AUTO
    return Tier.APPROVAL
