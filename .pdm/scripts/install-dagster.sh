#!/bin/bash

kubectl create secret generic dagster-cloud-agent-token \
  --save-config \
  --dry-run=client \
  --namespace=dagster-cloud \
  --from-literal=DAGSTER_CLOUD_AGENT_TOKEN="${DAGSTER_CLOUD_AGENT_TOKEN}" \
  --output=yaml |
  kubectl apply -f - ||
  true

helm repo add dagster-cloud https://dagster-io.github.io/helm-user-cloud
helm repo update

helm show values dagster-cloud/dagster-cloud-agent >.helm/dagster/values.yaml

helm upgrade \
  --install user-cloud dagster-cloud/dagster-cloud-agent \
  --namespace dagster-cloud \
  -f .helm/dagster/values-override.yaml
