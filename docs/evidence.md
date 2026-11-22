# Verification and evidence

This page separates checks encoded in the repository from outcomes that still need a repeatable cluster experiment.

## Automated checks in CI

| Area | Automated check | What it establishes |
|---|---|---|
| Python | Ruff lint and format check | Style and formatting constraints pass |
| Python | pytest -q | Unit tests for diagnosis, policy, runbooks and webhook behavior |
| Kubernetes | kubectl kustomize | Deployment manifests render |
| Kubernetes | kubeconform strict validation | Rendered manifests and chaos examples are schema-checked; missing schemas are ignored |
| Terraform | terraform fmt -check, init and validate | Example Terraform configuration is formatted and validates |
| Container | Docker Buildx build and Trivy scan | Image builds and HIGH/CRITICAL unfixed findings are checked |

Source: .github/workflows/ci.yml.

## Implemented scope visible in the repository

- Alertmanager webhook API and health/metrics endpoints.
- Context collection, rule-based diagnosis and optional local-LLM diagnosis.
- Policy modes and named runbooks with bounded parameters.
- Kubernetes deployment, service and scoped RBAC examples.
- Prometheus alerting/monitoring configuration and Argo CD application examples.
- Fault-injection manifests for bad image, crash loop and OOM scenarios.

## Not yet claimed as measured

No benchmark result, remediation success rate, mean recovery time, alert-to-action latency or production availability figure is published here. The scenario table remains unreported until a repeatable cluster experiment records inputs, timestamps, outcomes and recovery verification.

## Reproduce local unit checks

~~~bash
cd remediator
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest -q
~~~

## Next evidence to collect

1. Run each chaos scenario in a disposable k3s cluster.
2. Record the alert payload, diagnosis, policy decision and runbook result.
3. Verify recovery independently, for example rollout status and pod readiness.
4. Capture timestamps and repeat each scenario enough times to report a median and range.
5. Publish results only after the procedure is repeatable.
