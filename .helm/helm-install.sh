#!/bin/bash

helm repo add dagster-cloud https://dagster-io.github.io/helm-user-cloud
helm repo update

helm show values dagster-cloud/dagster-cloud-agent >.helm/values.yaml

helm upgrade \
  --install user-cloud dagster-cloud/dagster-cloud-agent \
  --namespace dagster-cloud \
  --set dagsterCloud.deployment=prod \
  -f .helm/values-override.yaml
