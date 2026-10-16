from pydantic import BaseModel, Field


class Alert(BaseModel):
    status: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    fingerprint: str | None = None

    @property
    def name(self) -> str:
        return self.labels.get("alertname", "unknown")

    @property
    def namespace(self) -> str | None:
        return self.labels.get("namespace")

    @property
    def pod(self) -> str | None:
        return self.labels.get("pod")


class AlertmanagerPayload(BaseModel):
    """Alertmanager webhook format (version 4)."""

    status: str
    alerts: list[Alert]
    receiver: str | None = None


class Context(BaseModel):
    alert: Alert
    owner_kind: str | None = None
    owner_name: str | None = None
    events: list[str] = Field(default_factory=list)
    logs: str = ""
    errors: list[str] = Field(default_factory=list)


class Diagnosis(BaseModel):
    runbook: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # "llm" or "rules"


class Result(BaseModel):
    alert: str
    target: str
    diagnosis: Diagnosis
    tier: str
    action: str
