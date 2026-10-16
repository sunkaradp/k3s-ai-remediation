"""Picks a runbook for an alert.

The LLM only chooses from the allowlist. If it is down, slow or returns
something outside the list, the rule-based fallback decides instead.
"""

import json
import logging
import os

import httpx

from app.models import Context, Diagnosis
from app.policy import RISK

log = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama.ai:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"

RULES = {
    "KubePodCrashLooping": ("restart_pod", "pod is crash looping", 0.6),
    "PodOOMKilled": ("increase_memory", "container was OOMKilled", 0.85),
    "KubePodImagePullFailed": ("rollback_deployment", "new image cannot be pulled", 0.8),
    "KubeDeploymentReplicasMismatch": ("scale_up", "not enough ready replicas", 0.5),
}

PROMPT = """You are an SRE on a k3s cluster. Pick ONE fix for the alert below.
Allowed runbooks: {runbooks}
Use "none" if no runbook is safe or you are unsure.

Alert: {alert}
Labels: {labels}
Owner: {owner}
Recent events:
{events}
Last log lines:
{logs}

Answer with JSON only: {{"runbook": "...", "reason": "one sentence", "confidence": 0.0-1.0}}"""


def by_rules(ctx: Context) -> Diagnosis:
    runbook, reason, conf = RULES.get(ctx.alert.name, ("none", "no rule for this alert", 0.0))
    return Diagnosis(runbook=runbook, reason=reason, confidence=conf, source="rules")


def build_prompt(ctx: Context) -> str:
    return PROMPT.format(
        runbooks=", ".join(RISK),
        alert=ctx.alert.name,
        labels=ctx.alert.labels,
        owner=f"{ctx.owner_kind}/{ctx.owner_name}",
        events="\n".join(ctx.events) or "(none)",
        logs=ctx.logs[-3000:] or "(none)",
    )


def parse(raw: str) -> Diagnosis | None:
    try:
        data = json.loads(raw)
        d = Diagnosis(**data, source="llm")
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return d if d.runbook in RISK else None


def by_llm(ctx: Context) -> Diagnosis | None:
    r = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": build_prompt(ctx),
            "format": "json",
            "stream": False,
        },
        timeout=60,
    )
    r.raise_for_status()
    return parse(r.json().get("response", ""))


def diagnose(ctx: Context) -> Diagnosis:
    if LLM_ENABLED:
        try:
            d = by_llm(ctx)
            if d:
                return d
            log.warning("LLM answer invalid, using rules")
        except Exception as e:
            log.warning("LLM failed (%s), using rules", e)
    return by_rules(ctx)
