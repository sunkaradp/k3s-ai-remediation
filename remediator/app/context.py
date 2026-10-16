"""Collects what an engineer would look at first: owner, recent events, last log lines."""

import logging
import os

import httpx

from app.models import Alert, Context

log = logging.getLogger(__name__)

LOKI_URL = os.getenv("LOKI_URL", "http://loki.monitoring:3100")
LOG_LINES = int(os.getenv("CONTEXT_LOG_LINES", "50"))


def _k8s():
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api()


def _find_owner(core, apps, namespace: str, pod: str) -> tuple[str | None, str | None]:
    p = core.read_namespaced_pod(pod, namespace)
    for ref in p.metadata.owner_references or []:
        if ref.kind == "ReplicaSet":
            rs = apps.read_namespaced_replica_set(ref.name, namespace)
            for rs_ref in rs.metadata.owner_references or []:
                if rs_ref.kind == "Deployment":
                    return "Deployment", rs_ref.name
        return ref.kind, ref.name
    return None, None


def _events(core, namespace: str, pod: str) -> list[str]:
    evs = core.list_namespaced_event(namespace, field_selector=f"involvedObject.name={pod}")
    return [f"{e.type} {e.reason}: {e.message}" for e in evs.items[-10:]]


def _loki_logs(namespace: str, pod: str) -> str:
    query = f'{{namespace="{namespace}", pod="{pod}"}}'
    r = httpx.get(
        f"{LOKI_URL}/loki/api/v1/query_range",
        params={"query": query, "limit": LOG_LINES, "direction": "backward"},
        timeout=5,
    )
    r.raise_for_status()
    lines = [v[1] for s in r.json()["data"]["result"] for v in s["values"]]
    return "\n".join(reversed(lines))


def collect(alert: Alert) -> Context:
    ctx = Context(alert=alert)
    if not (alert.namespace and alert.pod):
        ctx.errors.append("alert has no namespace/pod label")
        return ctx

    try:
        core, apps = _k8s()
        ctx.owner_kind, ctx.owner_name = _find_owner(core, apps, alert.namespace, alert.pod)
        ctx.events = _events(core, alert.namespace, alert.pod)
    except Exception as e:  # context is best effort, diagnosis still runs
        log.warning("k8s context failed: %s", e)
        ctx.errors.append(f"k8s: {e}")

    try:
        ctx.logs = _loki_logs(alert.namespace, alert.pod)
    except Exception as e:
        log.warning("loki context failed: %s", e)
        ctx.errors.append(f"loki: {e}")

    return ctx
