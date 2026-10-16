"""The only actions the remediator can take. Each one is small, reversible and logged."""

import logging
import os
from datetime import UTC, datetime

from app.models import Context

log = logging.getLogger(__name__)

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
MEMORY_STEP = float(os.getenv("MEMORY_STEP", "1.5"))
MEMORY_MAX_MI = int(os.getenv("MEMORY_MAX_MI", "2048"))
MAX_REPLICAS = int(os.getenv("MAX_REPLICAS", "5"))


def _apps():
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api()


def to_mi(value: str) -> int:
    units = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024}
    for suffix, factor in units.items():
        if value.endswith(suffix):
            return int(float(value[: -len(suffix)]) * factor)
    return int(int(value) / (1024 * 1024))  # plain bytes


def restart_pod(ctx: Context) -> str:
    ns, pod = ctx.alert.namespace, ctx.alert.pod
    if DRY_RUN:
        return f"[dry-run] would delete pod {ns}/{pod}"
    core, _ = _apps()
    core.delete_namespaced_pod(pod, ns)
    return f"deleted pod {ns}/{pod}"


def rollback_deployment(ctx: Context) -> str:
    """Same as `kubectl rollout undo`: copy the previous ReplicaSet template back."""
    if ctx.owner_kind != "Deployment":
        return "skipped: owner is not a Deployment"
    ns, name = ctx.alert.namespace, ctx.owner_name
    if DRY_RUN:
        return f"[dry-run] would roll back deployment {ns}/{name}"
    _, apps = _apps()
    dep = apps.read_namespaced_deployment(name, ns)
    selector = ",".join(f"{k}={v}" for k, v in dep.spec.selector.match_labels.items())
    rss = apps.list_namespaced_replica_set(ns, label_selector=selector).items
    rss.sort(key=lambda r: int(r.metadata.annotations["deployment.kubernetes.io/revision"]))
    if len(rss) < 2:
        return "skipped: no previous revision"
    template = rss[-2].spec.template
    template.metadata.labels.pop("pod-template-hash", None)
    apps.patch_namespaced_deployment(name, ns, {"spec": {"template": template}})
    return f"rolled back deployment {ns}/{name}"


def increase_memory(ctx: Context) -> str:
    if ctx.owner_kind != "Deployment":
        return "skipped: owner is not a Deployment"
    ns, name = ctx.alert.namespace, ctx.owner_name
    container = ctx.alert.labels.get("container")
    if DRY_RUN:
        return f"[dry-run] would raise memory limit x{MEMORY_STEP} on {ns}/{name}/{container}"
    _, apps = _apps()
    dep = apps.read_namespaced_deployment(name, ns)
    for c in dep.spec.template.spec.containers:
        if container and c.name != container:
            continue
        current = to_mi((c.resources.limits or {}).get("memory", "256Mi"))
        new = min(int(current * MEMORY_STEP), MEMORY_MAX_MI)
        if new <= current:
            return f"skipped: {c.name} already at max {MEMORY_MAX_MI}Mi"
        patch = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"name": c.name, "resources": {"limits": {"memory": f"{new}Mi"}}}
                        ]
                    }
                }
            }
        }
        apps.patch_namespaced_deployment(name, ns, patch)
        return f"memory {c.name}: {current}Mi -> {new}Mi"
    return "skipped: container not found"


def scale_up(ctx: Context) -> str:
    if ctx.owner_kind != "Deployment":
        return "skipped: owner is not a Deployment"
    ns, name = ctx.alert.namespace, ctx.owner_name
    if DRY_RUN:
        return f"[dry-run] would add 1 replica to {ns}/{name}"
    _, apps = _apps()
    current = apps.read_namespaced_deployment_scale(name, ns).spec.replicas
    if current >= MAX_REPLICAS:
        return f"skipped: already at {MAX_REPLICAS} replicas"
    apps.patch_namespaced_deployment_scale(name, ns, {"spec": {"replicas": current + 1}})
    return f"scaled {ns}/{name}: {current} -> {current + 1}"


RUNBOOKS = {
    "restart_pod": restart_pod,
    "rollback_deployment": rollback_deployment,
    "increase_memory": increase_memory,
    "scale_up": scale_up,
}


def run(name: str, ctx: Context) -> str:
    fn = RUNBOOKS.get(name)
    if fn is None:
        return "no action"
    started = datetime.now(UTC).isoformat()
    result = fn(ctx)
    log.info("runbook=%s started=%s result=%s", name, started, result)
    return result
