# Dagster GKE Best Practices Hardening

**Date:** 2026-03-27 **Status:** Approved **Scope:**
`.k8s/dagster/values-override.yaml`, Terraform alerting (new)

## Problem Statement

The Dagster Cloud Hybrid deployment on GKE Autopilot has three categories of
issues:

1. **Reliability:** Both agent replicas can be killed simultaneously by spot
   preemption. The PDB only protects against voluntary disruptions, and the
   current pod anti-affinity only ensures different hostnames — not different
   zones. Correlated zone-level preemption can take out both agents.

2. **Operational maturity:** No alerting on K8s-level events (spot evictions,
   OOM kills, PDB violations, prolonged pod pending). Workspace and run pods
   lack container security contexts. No restrictions on code-level K8s config
   overrides.

3. **Cost:** ARM64 spot is the right strategy and stays. No cost changes
   proposed — this is about not wasting money on avoidable incident response.

## Design

### 1. Agent Resilience: Topology Spread + Readiness Probe

**Replace** the hostname-level pod anti-affinity with zone-level topology spread
constraints. This ensures the 2 agent replicas land in different GCE zones,
reducing the probability of correlated spot preemption.

Remove the existing `affinity` block (pod anti-affinity on
`kubernetes.io/hostname`) entirely — zone-level spread subsumes it (different
zones = different nodes).

```yaml
dagsterCloudAgent:
  # affinity: <removed>
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule
      labelSelector:
        matchLabels:
          app.kubernetes.io/name: dagster-cloud-agent
```

**Enable** the readiness probe and rolling update strategy for zero-downtime
Helm upgrades. The probe checks for completion of the initial reconciliation
loop before the pod is considered ready.

```yaml
dagsterCloudAgent:
  readinessProbe:
    exec:
      command:
        - /bin/bash
        - -c
        - test -f /tmp/finished_initial_reconciliation_sentinel.txt
    failureThreshold: 60
    initialDelaySeconds: 0
    periodSeconds: 10

  deploymentStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0%
      maxSurge: 200%
```

With `maxUnavailable: 0%` and `maxSurge: 200%`, Kubernetes spins up a new
replica and waits for it to pass the readiness probe before terminating the old
one. Combined with the PDB (`maxUnavailable: 1`), this guarantees at least one
agent is always serving during upgrades.

**Replica count stays at 2.** Revisit bumping to 3 if simultaneous evictions
persist after the zone spread change.

### 2. Security Contexts on Workspace and Run Pods

Add container-level security context to both `serverK8sConfig` and
`runK8sConfig`:

```yaml
containerConfig:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1234
    runAsGroup: 1234
    allowPrivilegeEscalation: false
    capabilities:
      drop:
        - ALL
```

- `runAsUser`/`runAsGroup` 1234 matches the `teamster` user created in the
  Dockerfile.
- `readOnlyRootFilesystem` is intentionally omitted — dbt and Dagster write to
  `/tmp` and other paths. Enabling it would require explicit `emptyDir` mounts,
  which is a separate hardening effort.

### 3. Code-Level K8s Config Restriction

Add `onlyAllowUserDefinedK8sConfigFields` to prevent `dagster-k8s/config` tags
in code from overriding sensitive K8s fields (volumes, service accounts,
security contexts):

```yaml
workspace:
  onlyAllowUserDefinedK8sConfigFields:
    containerConfig:
      resources: true
      env: true
    podSpecConfig:
      nodeSelector: true
    podTemplateSpecMetadata:
      annotations: true
    jobSpecConfig:
      ttlSecondsAfterFinished: true
    jobMetadata:
      annotations: true
```

Only resource requests/limits, environment variables, node selectors,
annotations, and job TTL can be set from code. Everything else is locked to the
Helm chart values.

### 4. GKE Alerting (Terraform)

Create GCP Cloud Monitoring alert policies as Terraform resources. This aligns
with the planned IaC initiative for GCP infrastructure.

**Alert policies:**

| Alert             | Metric/Condition                                           | Threshold                                            |
| ----------------- | ---------------------------------------------------------- | ---------------------------------------------------- |
| Pod restart storm | `kubernetes.io/container/restart_count` rate               | > 3 restarts in 10 min for agent or code server pods |
| OOM kill          | Container `reason = OOMKilled`                             | Any occurrence                                       |
| PDB at limit      | `kubernetes.io/poddisruptionbudget/pods_disrupted_allowed` | = 0 for > 5 min                                      |
| Pod stuck pending | Pod phase = `Pending`                                      | > 5 min in `dagster-cloud` namespace                 |

**Notification channel:** To be determined during implementation (Slack webhook,
email, or PagerDuty).

**Terraform scope:** Alert policies only. The GKE cluster, Helm releases, and
1Password Connect remain managed by their existing shell scripts. Migrating
those to Terraform is out of scope for this project.

## Out of Scope

- Changing ARM64 node architecture (cost advantage confirmed)
- Changing replica count (stays at 2, revisit if issues persist)
- `readOnlyRootFilesystem` (requires emptyDir mount planning)
- Branch deployment TTL tuning
- Migrating existing K8s resources (cluster, Helm releases) to Terraform
- Image pre-pull / image streaming optimization (limited value on Autopilot)

## Risks

- **Topology spread on Autopilot:** Autopilot manages node provisioning. If only
  one zone has spot capacity, the second agent pod could remain Pending with
  `DoNotSchedule`. Mitigation: monitor pod pending alerts, consider relaxing to
  `ScheduleAnyway` if this becomes an issue.
- **Helm chart support for topology spread:** The `dagsterCloudAgent` section
  may not have a native `topologySpreadConstraints` field — verify during
  implementation. May need to use `additionalPodSpecConfig` or a similar escape
  hatch.
- **`onlyAllowUserDefinedK8sConfigFields`:** If existing code locations use
  `dagster-k8s/config` tags for fields not in the whitelist, those runs will
  fail after this change. Audit code locations before enabling.

## Implementation Order

1. Audit code locations for existing `dagster-k8s/config` tag usage
2. Apply security contexts to `values-override.yaml`
3. Apply `onlyAllowUserDefinedK8sConfigFields`
4. Replace anti-affinity with topology spread constraints
5. Enable readiness probe and rolling update strategy
6. Verify Helm chart supports all fields (check values.yaml schema)
7. Deploy via `helm upgrade` and validate
8. Create Terraform project/module for GKE alerting
9. Define and deploy alert policies
10. Document runbook for common alert scenarios
