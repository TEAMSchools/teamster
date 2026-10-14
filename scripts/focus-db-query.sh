#!/usr/bin/env bash
# Run a read-only SQL file against the Focus Postgres database (Miami) from a
# throwaway pod in the GKE cluster. Focus allowlists the cluster's egress IP, so
# the codespace cannot connect directly. Credentials come from the
# op-focus-db-kippmiami secret and never leave the cluster.
#
# The connection goes through PgBouncer, which rejects startup options, so put
# read-only and timeout settings inside the SQL file:
#   begin transaction read only;
#   set local statement_timeout = '5min';
#   ...
#   rollback;
#
# Usage: bash scripts/focus-db-query.sh <file.sql>
# Needs a kubectl context on the Dagster GKE cluster.
set -euo pipefail

if [[ $# -ne 1 || ! -f ${1} ]]; then
	echo "usage: ${0} <file.sql>" >&2
	exit 2
fi

ns=dagster-cloud
name="focus-db-query-$(date +%s)"

cleanup() {
	kubectl -n "${ns}" delete pod "${name}" --ignore-not-found --wait=false >/dev/null
	kubectl -n "${ns}" delete configmap "${name}" --ignore-not-found >/dev/null
}
trap cleanup EXIT

# The SQL is mounted from a ConfigMap and the result read from the pod log.
# `kubectl run -i --rm` loses the error when psql fails before the attach.
kubectl -n "${ns}" create configmap "${name}" --from-file=query.sql="${1}" >/dev/null

# psql reads the PG* variables natively, so no secret value is expanded in a shell.
kubectl -n "${ns}" apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: ${name}
spec:
  restartPolicy: Never
  containers:
    - name: psql
      image: postgres:16-alpine
      command: ["psql", "-X", "-v", "ON_ERROR_STOP=1", "--echo-queries", "-f", "/sql/query.sql"]
      resources:
        requests: {cpu: 250m, memory: 256Mi}
      volumeMounts:
        - {name: sql, mountPath: /sql}
      env:
        - {name: PGHOST,     valueFrom: {secretKeyRef: {name: op-focus-db-kippmiami, key: host}}}
        - {name: PGPORT,     valueFrom: {secretKeyRef: {name: op-focus-db-kippmiami, key: port}}}
        - {name: PGDATABASE, valueFrom: {secretKeyRef: {name: op-focus-db-kippmiami, key: database}}}
        - {name: PGUSER,     valueFrom: {secretKeyRef: {name: op-focus-db-kippmiami, key: username}}}
        - {name: PGPASSWORD, valueFrom: {secretKeyRef: {name: op-focus-db-kippmiami, key: password}}}
        - {name: PGSSLMODE,  value: require}
        - {name: PGCONNECT_TIMEOUT, value: "30"}
  volumes:
    - name: sql
      configMap: {name: ${name}}
YAML

echo "Waiting for ${name} (Autopilot may take a few minutes to schedule it)..." >&2
phase=Pending
for _ in $(seq 1 120); do
	phase=$(kubectl -n "${ns}" get pod "${name}" -o jsonpath='{.status.phase}')
	case "${phase}" in
	Succeeded | Failed) break ;;
	*) sleep 5 ;;
	esac
done

kubectl -n "${ns}" logs "${name}"
echo "--- pod phase: ${phase}" >&2
[[ ${phase} == Succeeded ]]
