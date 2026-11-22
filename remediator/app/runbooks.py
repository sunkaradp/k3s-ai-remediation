"""Allowlisted, dry-run-first Kubernetes remediation runbooks."""

import logging
import os
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from app.models import Context

log = logging.getLogger(__name__)

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
MEMORY_STEP = float(os.getenv("MEMORY_STEP", "1.5"))
MEMORY_MAX_MI = int(os.getenv("MEMORY_MAX_MI", "2048"))
MAX_REPLICAS = int(os.getenv("MAX_REPLICAS", "5"))

if MEMORY_STEP <= 1:
    raise ValueError("MEMORY_STEP must be greater than 1")
if MEMORY_MAX_MI < 1 or MAX_REPLICAS < 1:
    raise ValueError("MEMORY_MAX_MI and MAX_REPLICAS must be positive")


def _allowed(ctx: Context) -> bool:
    """Fail closed unless the alert namespace is explicitly allowlisted."""
    allowed = {
        item.strip()
        for item in os.getenv("REMEDIATION_ALLOWED_NAMESPACES", "").split(",")
        if item.strip()
    }
    namespace = ctx.alert.namespace
    if not namespace or namespace not in allowed:
        log.warning("deny remediation: namespace %r is not allowlisted", namespace)
        return False
    return True


def _apps():
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api()


def to_mi(value: str) -> int:
    """Convert common Kubernetes memory quantities to whole mebibytes."""
    quantity = str(value).strip()
    units = {
        "Ki": Decimal(1) / Decimal(1024),
        "Mi": Decimal(1),
        "Gi": Decimal(1024),
        "Ti": Decimal(1024 * 1024),
    }
    try:
        for suffix, factor in units.items():
            if quantity.endswith(suffix):
                amount = Decimal(quantity[: -len(suffix)]) * factor
                break
        else:
            amount = Decimal(quantity) / Decimal(1024 * 1024)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid memory quantity: {value!r}") from exc

    if not amount.is_finite() or amount < 0:
        raise ValueError(f"invalid memory quantity: {value!r}")
    return int(amount)


def restart_pod(ctx: Context) -> str:
    namespace, pod = ctx.alert.namespace, ctx.alert.pod
    if not _allowed(ctx):
        return "skipped: namespace is not allowlisted"
    if not pod:
        return "skipped: alert is missing pod"
    if DRY_RUN:
        return f"[dry-run] would delete pod {namespace}/{pod}"

    core, _ = _apps()
    core.delete_namespaced_pod(pod, namespace)
    return f"deleted pod {namespace}/{pod}"


def rollback_deployment(ctx: Context) -> str:
    if not _allowed(ctx):
        return "skipped: namespace is not allowlisted"
    if ctx.owner_kind != "Deployment" or not ctx.owner_name:
        return "skipped: owner is not a Deployment"

    namespace, name = ctx.alert.namespace, ctx.owner_name
    if DRY_RUN:
        return f"[dry-run] would roll back deployment {namespace}/{name}"

    from kubernetes import client

    _, apps = _apps()
    deployment = apps.read_namespaced_deployment(name, namespace)
    selector = ",".join(
        f"{key}={value}"
        for key, value in (deployment.spec.selector.match_labels or {}).items()
    )
    replica_sets = apps.list_namespaced_replica_set(
        namespace,
        label_selector=selector,
    ).items

    deployment_uid = deployment.metadata.uid
    revisions = []
    for replica_set in replica_sets:
        annotations = replica_set.metadata.annotations or {}
        revision = annotations.get("deployment.kubernetes.io/revision", "")
        owned_by_deployment = any(
            owner.kind == "Deployment"
            and owner.name == name
            and (not deployment_uid or owner.uid == deployment_uid)
            for owner in (replica_set.metadata.owner_references or [])
        )
        if owned_by_deployment and revision.isdigit():
            revisions.append((int(revision), replica_set))

    revisions.sort(key=lambda item: item[0])
    if len(revisions) < 2:
        return "skipped: no previous revision"

    previous_template = revisions[-2][1].spec.template
    template = client.ApiClient().sanitize_for_serialization(previous_template)
    labels = template.get("metadata", {}).get("labels", {})
    labels.pop("pod-template-hash", None)
    apps.patch_namespaced_deployment(
        name,
        namespace,
        {"spec": {"template": template}},
    )
    return f"rolled back deployment {namespace}/{name}"


def increase_memory(ctx: Context) -> str:
    if not _allowed(ctx):
        return "skipped: namespace is not allowlisted"
    if ctx.owner_kind != "Deployment" or not ctx.owner_name:
        return "skipped: owner is not a Deployment"

    namespace, name = ctx.alert.namespace, ctx.owner_name
    container_name = ctx.alert.labels.get("container")
    if not container_name:
        return "skipped: alert is missing container label"
    if DRY_RUN:
        return (
            f"[dry-run] would raise memory limit x{MEMORY_STEP} "
            f"on {namespace}/{name}/{container_name}"
        )

    _, apps = _apps()
    deployment = apps.read_namespaced_deployment(name, namespace)
    for container in deployment.spec.template.spec.containers:
        if container.name != container_name:
            continue

        limits = container.resources.limits or {}
        current = to_mi(limits.get("memory", "256Mi"))
        new = min(int(current * MEMORY_STEP), MEMORY_MAX_MI)
        if new <= current:
            return f"skipped: {container.name} already at max {MEMORY_MAX_MI}Mi"

        patch = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container.name,
                                "resources": {"limits": {"memory": f"{new}Mi"}},
                            }
                        ]
                    }
                }
            }
        }
        apps.patch_namespaced_deployment(name, namespace, patch)
        return f"memory {container.name}: {current}Mi -> {new}Mi"

    return "skipped: container not found"


def scale_up(ctx: Context) -> str:
    if not _allowed(ctx):
        return "skipped: namespace is not allowlisted"
    if ctx.owner_kind != "Deployment" or not ctx.owner_name:
        return "skipped: owner is not a Deployment"

    namespace, name = ctx.alert.namespace, ctx.owner_name
    if DRY_RUN:
        return f"[dry-run] would add 1 replica to {namespace}/{name}"

    _, apps = _apps()
    current = apps.read_namespaced_deployment_scale(name, namespace).spec.replicas or 0
    if current >= MAX_REPLICAS:
        return f"skipped: already at {MAX_REPLICAS} replicas"

    apps.patch_namespaced_deployment_scale(
        name,
        namespace,
        {"spec": {"replicas": current + 1}},
    )
    return f"scaled {namespace}/{name}: {current} -> {current + 1}"


RUNBOOKS = {
    "restart_pod": restart_pod,
    "rollback_deployment": rollback_deployment,
    "increase_memory": increase_memory,
    "scale_up": scale_up,
}


def run(name: str, ctx: Context) -> str:
    runbook = RUNBOOKS.get(name)
    if runbook is None:
        return "no action"

    started = datetime.now(UTC).isoformat()
    result = runbook(ctx)
    log.info("runbook=%s started=%s result=%s", name, started, result)
    return result
