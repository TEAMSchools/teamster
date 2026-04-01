# Dagster GKE Best Practices Hardening

**Date:** 2026-03-27 **Updated:** 2026-04-01 **Status:** Approved **Scope:**
`.k8s/dagster/values-override.yaml`

> **Update (2026-04-01):** Spec revised throughout to reflect the node
> scheduling fallback strategy implemented on `main` after a sustained GCE
> STOCKOUT in us-central1 on 2026-03-30/31. Hard `nodeSelector` constraints were
> replaced with weighted `nodeAffinity` preferences across all pod types. GKE
> alerting (Section 4) moved to the Terraform IaC spec
> (TEAMSchools/teamster#3550). See Risks section for the spot STOCKOUT incident
> and on-demand fallback tradeoff.

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

4. **Capacity exhaustion:** A sustained GCE STOCKOUT on 2026-03-30/31 revealed
   that hard `nodeSelector` constraints (Scale-Out + arm64) cause pods to stay
   Pending indefinitely when the requested compute class is unavailable. 28
   `ScaleUpFailed` events over ~10 hours caused OOM evictions, scheduling
   failures, and sensor tick errors across multiple code locations.

## Design

### 1. Agent Resilience: Topology Spread + Readiness Probe

> **Already implemented (partial):** All pod types now use weighted
> `nodeAffinity` preferences instead of hard `nodeSelector`. The existing
> `podAntiAffinity` on `kubernetes.io/hostname` was preserved. This section
> proposes adding zone-level topology spread on top of the current affinity
> structure.
>
> Current scheduling weights (see [`.k8s/CLAUDE.md`](../../../.k8s/CLAUDE.md)
> for full details):
>
> | Weight | Agent (x86-only) | Code server     | Run pod         |
> | ------ | ---------------- | --------------- | --------------- |
> | 50     | Spot             | Spot            | —               |
> | 40     | —                | Scale-Out arm64 | Scale-Out arm64 |
> | 30     | General-Purpose  | General-Purpose | General-Purpose |
> | 20     | Scale-Out        | Scale-Out x86   | Scale-Out x86   |
> | 10     | Balanced         | Balanced        | Balanced        |
>
> Run pods exclude spot (`safe-to-evict: "false"` is mutually exclusive with
> spot on Autopilot). Agent pods exclude arm64 tiers (image is x86-only).

**Add** zone-level topology spread constraints alongside the existing affinity
block. The `podAntiAffinity` ensures different hostnames; topology spread adds
cross-zone distribution to reduce correlated spot preemption.

```yaml
dagsterCloudAgent:
  affinity:
    nodeAffinity:
      # ... existing weighted preferences (spot, GP, Scale-Out, Balanced)
    podAntiAffinity:
      # ... existing hostname anti-affinity (preserved)
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

> **Note:** `nodeSelector` is retained in the allowlist even though global
> scheduling now uses `nodeAffinity` preferences. Per-location
> `server_k8s_config` in `dagster-cloud.yaml` deep-merges with global
> `serverK8sConfig`, so code locations may still need `nodeSelector` for
> location-specific constraints (e.g., `podAntiAffinity` is set per-location).

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

### 4. GKE Alerting

Moved to the
[Terraform IaC design spec](2026-03-30-terraform-infrastructure-as-code-design.md)
(`alerting/` module) — alert policies are Terraform resources, not Helm/YAML
config. See TEAMSchools/teamster#3550.

## Out of Scope

- Changing ARM64 node architecture (cost advantage confirmed)
- Changing replica count (stays at 2, revisit if issues persist)
- `readOnlyRootFilesystem` (requires emptyDir mount planning)
- Branch deployment TTL tuning
- Migrating existing K8s resources (cluster, Helm releases) to Terraform
- Image pre-pull / image streaming optimization (limited value on Autopilot, but
  cold starts on fallback on-demand nodes may be slower without cached images —
  worth monitoring after the scheduling fallback is exercised in production)

## Risks

- **Spot STOCKOUT and on-demand fallback (realized 2026-03-30/31):** A sustained
  GCE `RESOURCE_POOL_EXHAUSTED` across zones `a`, `b`, and `f` in us-central1
  caused ~10 hours of scheduling failures. Hard `nodeSelector` constraints meant
  pods could not fall back to alternative compute classes. **Mitigated:** all
  pod types now use weighted `nodeAffinity` preferences instead of
  `nodeSelector`, allowing Autopilot to schedule on any available compute class.
  **Tradeoff:** on-demand nodes cost more than spot — but Autopilot bills
  per-pod, so the cost difference is limited to the spot discount (~60-91%)
  during the fallback window. Availability during overnight batch runs is worth
  the cost.
- **Topology spread on Autopilot:** Autopilot manages node provisioning. If only
  one zone has spot capacity, the second agent pod could remain Pending with
  `DoNotSchedule`. Note that `DoNotSchedule` combined with a multi-zone STOCKOUT
  (as seen on 2026-03-30/31) would be _worse_ than no topology spread — it would
  prevent even single-zone scheduling. Mitigation: monitor pod pending alerts
  (and the new scale-up failure alert), and be prepared to relax to
  `ScheduleAnyway` if multi-zone unavailability recurs.
- **Helm chart support for topology spread:** The `dagsterCloudAgent` section
  may not have a native `topologySpreadConstraints` field — verify during
  implementation. May need to use `additionalPodSpecConfig` or a similar escape
  hatch.
- **`onlyAllowUserDefinedK8sConfigFields`:** If existing code locations use
  `dagster-k8s/config` tags for fields not in the whitelist, those runs will
  fail after this change. Audit code locations before enabling.

## Implementation Order

1. ~~Replace `nodeSelector` with weighted `nodeAffinity` preferences~~ — **done
   (2026-03-31, 2026-04-01)**, applied directly to `main`
2. ~~Add `--dry-run` + confirmation prompt to install scripts~~ — **done
   (2026-03-31)**, applied directly to `main`
3. Audit code locations for existing `dagster-k8s/config` tag usage
4. Apply security contexts to `values-override.yaml`
5. Apply `onlyAllowUserDefinedK8sConfigFields`
6. Add topology spread constraints to agent pods (alongside existing affinity)
7. Enable readiness probe and rolling update strategy
8. Verify Helm chart supports all fields (check values.yaml schema)
9. Deploy via `helm upgrade --dry-run` and validate, then apply
10. GKE alerting — see Terraform IaC spec (TEAMSchools/teamster#3550)
