#!/usr/bin/env bash
# Usage: ./chaos/run.sh oomkill|crashloop|bad-image|clean
set -euo pipefail
cd "$(dirname "$0")"

kubectl create namespace chaos --dry-run=client -o yaml | kubectl apply -f -

case "${1:-}" in
  oomkill)   kubectl apply -f oomkill.yaml ;;
  crashloop) kubectl apply -f crashloop.yaml ;;
  bad-image)
    kubectl apply -f bad-image.yaml
    kubectl -n chaos rollout status deploy/chaos-image --timeout=120s
    kubectl -n chaos set image deploy/chaos-image web=nginx:does-not-exist
    ;;
  clean)     kubectl delete namespace chaos --wait=false ;;
  *) echo "usage: $0 oomkill|crashloop|bad-image|clean"; exit 1 ;;
esac

echo "Injected: ${1}. Started at $(date -u +%FT%TZ). Watch with:"
echo "  kubectl -n remediation logs deploy/remediator -f | grep audit"
