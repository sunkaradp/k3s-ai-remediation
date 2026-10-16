import json
import logging

from fastapi import FastAPI
from prometheus_client import Counter, Histogram, make_asgi_app

from app import context, diagnose, runbooks
from app.models import AlertmanagerPayload, Result
from app.policy import Tier, decide

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("remediator")

ALERTS = Counter("remediator_alerts_total", "Alerts received", ["alertname"])
DECISIONS = Counter("remediator_decisions_total", "Decisions", ["runbook", "tier", "source"])
LATENCY = Histogram("remediator_handle_seconds", "Time to handle one alert")

app = FastAPI(title="k3s-ai-remediation")
app.mount("/metrics", make_asgi_app())


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/webhook/alertmanager")
def webhook(payload: AlertmanagerPayload) -> list[Result]:
    results = []
    for alert in payload.alerts:
        if alert.status != "firing":
            continue
        ALERTS.labels(alert.name).inc()
        with LATENCY.time():
            ctx = context.collect(alert)
            diag = diagnose.diagnose(ctx)
            tier = decide(diag.runbook, diag.confidence)

            if tier == Tier.AUTO:
                action = runbooks.run(diag.runbook, ctx)
            elif tier == Tier.APPROVAL:
                action = "waiting for approval"  # Slack approval comes in milestone 3
            else:
                action = "observed only"

        DECISIONS.labels(diag.runbook, tier, diag.source).inc()
        result = Result(
            alert=alert.name,
            target=f"{alert.namespace}/{alert.pod}",
            diagnosis=diag,
            tier=tier,
            action=action,
        )
        log.info("audit %s", json.dumps(result.model_dump()))
        results.append(result)
    return results
