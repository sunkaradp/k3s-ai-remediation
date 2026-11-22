# Architecture

This diagram describes components present in the repository and their intended interactions. It is not a claim that the full cluster deployment has been validated end to end.

~~~mermaid
flowchart LR
  subgraph Signals
    P[Prometheus] --> AM[Alertmanager]
    L[Loki]
  end
  AM -->|webhook| API[FastAPI remediator]
  API --> CTX[Context collection]
  CTX <--> K[Kubernetes API]
  CTX <--> L
  API --> D[Rule-based / optional local-LLM diagnosis]
  D --> G{Policy evaluation}
  G -->|OBSERVE| A[Audit / response only]
  G -->|APPROVAL| H[Human approval path]
  G -->|Eligible AUTO action| R[Allowlisted runbook]
  R --> K
  API --> M[Prometheus metrics]
~~~

## Trust boundaries

- Alert payloads and collected cluster/log context are inputs, not executable instructions.
- Diagnosis returns a constrained recommendation; the policy layer determines the permitted mode.
- Runbooks are predefined operations. The model does not receive arbitrary shell access.
- OBSERVE and DRY_RUN=true are the safe starting configuration.
- Approval integration and end-to-end cluster deployment remain roadmap work; the diagram does not imply they have been verified in a live cluster.

## Repository evidence

- API and decision logic: remediator/app/
- Unit tests: remediator/tests/
- Kubernetes manifests and RBAC: deploy/remediator/
- Monitoring configuration: monitoring/
- GitOps examples: gitops/argocd/
- Infrastructure example: terraform/
- CI workflow: .github/workflows/ci.yml
