#!/bin/bash

kubectl create namespace dagster-cloud
kubectl create secret generic dagster-cloud-agent-token \
	--save-config \
	--dry-run=client \
	--from-literal=DAGSTER_CLOUD_AGENT_TOKEN="${DAGSTER_CLOUD_AGENT_TOKEN}" \
	--namespace dagster-cloud \
	-o yaml |
	kubectl apply -f - ||
	true
