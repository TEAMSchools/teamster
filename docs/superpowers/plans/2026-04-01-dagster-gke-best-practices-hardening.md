# Dagster GKE Best Practices Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Dagster Cloud Hybrid deployment on GKE Autopilot with
topology spread, readiness probe, security contexts, and K8s config
restrictions.

**Architecture:** All changes are YAML edits to the Helm values override file
(`.k8s/dagster/values-override.yaml`). The Helm chart already supports every
field we need — `readinessProbe`, `deploymentStrategy`,
`additionalPodSpecConfig`, `securityContext`, and
`onlyAllowUserDefinedK8sConfigFields`. Deployment uses the existing
`install.sh`, which runs `helm upgrade --dry-run` before applying.

**Tech Stack:** Kubernetes (GKE Autopilot), Helm (dagster-cloud-agent chart),
YAML

**Spec:**
`docs/superpowers/specs/2026-03-27-dagster-gke-best-practices-design.md`
**Issue:** TEAMSchools/teamster#3539

---

## File Map

| File                                | Action | Responsibility               |
| ----------------------------------- | ------ | ---------------------------- |
| `.k8s/dagster/values-override.yaml` | Modify | All K8s config changes       |
| `.k8s/CLAUDE.md`                    | Modify | Document new config sections |

## Pre-Implementation: Audit Results

The spec requires auditing all `dagster-k8s/config` tag usage before enabling
`onlyAllowUserDefinedK8sConfigFields`. This audit is complete:

**All `dagster-k8s/config` tags in code use only `container_config.resources`:**

- `src/teamster/code_locations/kippnewark/dbt/assets.py:16` — CPU limits
- `src/teamster/code_locations/kippmiami/dbt/assets.py:16` — CPU limits
- `src/teamster/code_locations/kippcamden/dbt/assets.py:16` — CPU limits
- `src/teamster/code_locations/kipppaterson/dbt/assets.py:16` — CPU limits
- `src/teamster/code_locations/kipptaf/dbt/assets.py:22,38,53` — CPU limits
- `src/teamster/code_locations/kipptaf/tableau/assets.py:27` — memory limits
- `src/teamster/code_locations/kippnewark/powerschool/config/assets-transactiondate.yaml:5,14`
  — CPU/memory
- `src/teamster/code_locations/kippnewark/powerschool/config/assets-gradebook-monthly.yaml:6`
  — CPU/memory
- `src/teamster/code_locations/kipptaf/dlt/illuminate/config/illuminate.yaml:15,25,49`
  — CPU/memory

**All per-location `dagster-cloud.yaml` files use `server_k8s_config` with:**

- `pod_spec_config.affinity.podAntiAffinity` — all 5 locations
- `container_config.env` — all 5 locations

## Spec Deviation: `onlyAllowUserDefinedK8sConfigFields` Whitelist

The spec's whitelist is missing `podSpecConfig.affinity`. All 5 per-location
`dagster-cloud.yaml` files set `server_k8s_config.pod_spec_config.affinity` for
`podAntiAffinity`. Without whitelisting this field, per-location anti-affinity
will be silently blocked after this change, causing code server pods to
co-schedule on the same node.

**Fix:** Add `affinity: true` under `podSpecConfig` in the whitelist.

---

### Task 1: Add Security Contexts to Workspace and Run Pods

**Files:**

- Modify: `.k8s/dagster/values-override.yaml:96-108` (serverK8sConfig)
- Modify: `.k8s/dagster/values-override.yaml:160-173` (runK8sConfig)

- [ ] **Step 1: Add container security context to `serverK8sConfig`**

In `.k8s/dagster/values-override.yaml`, add `securityContext` inside the
existing `containerConfig` block for `serverK8sConfig`, after `resources`:

```yaml
serverK8sConfig:
  containerConfig:
    resources:
      requests:
        cpu: 500m
        memory: 2.0Gi
      limits:
        cpu: 750m
        memory: 2.5Gi
    securityContext:
      runAsNonRoot: true
      runAsUser: 1234
      runAsGroup: 1234
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL
```

`runAsUser`/`runAsGroup` 1234 matches the `teamster` user in the Dockerfile
(line 20: `useradd -m -u 1234 -g teamster teamster`).

- [ ] **Step 2: Add container security context to `runK8sConfig`**

Add the identical `securityContext` block inside the existing `containerConfig`
for `runK8sConfig`, after `resources`:

```yaml
runK8sConfig:
  containerConfig:
    resources:
      requests:
        cpu: 500m
        memory: 2.0Gi
      limits:
        cpu: 750m
        memory: 2.5Gi
    securityContext:
      runAsNonRoot: true
      runAsUser: 1234
      runAsGroup: 1234
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL
```

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "feat(k8s): add container security contexts to workspace and run pods"
```

---

### Task 2: Add `onlyAllowUserDefinedK8sConfigFields`

**Files:**

- Modify: `.k8s/dagster/values-override.yaml` (under `workspace:`, after
  `serverTTL`)

- [ ] **Step 1: Add the config restriction block**

Add after the `serverTTL` block (around line 222), before `extraManifests`:

```yaml
onlyAllowUserDefinedK8sConfigFields:
  containerConfig:
    resources: true
    env: true
  podSpecConfig:
    nodeSelector: true
    affinity: true
  podTemplateSpecMetadata:
    annotations: true
  jobSpecConfig:
    ttlSecondsAfterFinished: true
  jobMetadata:
    annotations: true
```

Note: `affinity: true` is added beyond what the spec lists — see "Spec
Deviation" section above. Without it, per-location `podAntiAffinity` in all 5
`dagster-cloud.yaml` files would be silently blocked.

`nodeSelector` is retained per the spec note — per-location configs may still
need it.

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "feat(k8s): restrict user-defined K8s config fields to safe whitelist"
```

---

### Task 3: Add Topology Spread Constraints to Agent Pods

**Files:**

- Modify: `.k8s/dagster/values-override.yaml:30-87` (dagsterCloudAgent section)

The Helm chart has no native `topologySpreadConstraints` field on
`dagsterCloudAgent`. The chart provides `additionalPodSpecConfig` (values.yaml
line 255) as an escape hatch for arbitrary pod spec fields.

- [ ] **Step 1: Add `additionalPodSpecConfig` with topology spread**

Add after the `affinity` block in the `dagsterCloudAgent` section (after the
closing of `podAntiAffinity`, around line 87):

```yaml
additionalPodSpecConfig:
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: ScheduleAnyway
      labelSelector:
        matchLabels:
          app.kubernetes.io/name: dagster-cloud-agent
```

`ScheduleAnyway` prefers cross-zone distribution but allows same-zone during
capacity exhaustion. Changed from `DoNotSchedule` during review — the
2026-03-30/31 STOCKOUT showed that hard constraints worsen multi-zone
unavailability.

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "feat(k8s): add zone topology spread constraints to agent pods"
```

---

### Task 4: Enable Readiness Probe and Rolling Update Strategy

**Files:**

- Modify: `.k8s/dagster/values-override.yaml:30-45` (dagsterCloudAgent section)

- [ ] **Step 1: Add readiness probe**

Add after `terminationGracePeriodSeconds: 15` in the `dagsterCloudAgent`
section:

```yaml
readinessProbe:
  exec:
    command:
      - /bin/bash
      - -c
      - test -f /tmp/finished_initial_reconciliation_sentinel.txt
  failureThreshold: 60
  initialDelaySeconds: 0
  periodSeconds: 10
```

The probe checks for the sentinel file written after the agent's first
reconciliation loop. With `failureThreshold: 60` and `periodSeconds: 10`, the
probe allows up to 10 minutes for initial reconciliation before marking the pod
unhealthy.

- [ ] **Step 2: Add rolling update strategy**

Add after the `readinessProbe` block:

```yaml
deploymentStrategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0%
    maxSurge: 200%
```

With `maxUnavailable: 0%` and `maxSurge: 200%`, Kubernetes spins up new replicas
and waits for readiness before terminating old ones. Combined with the PDB
(`maxUnavailable: 1`), this guarantees at least one agent is always serving
during upgrades.

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "feat(k8s): enable readiness probe and rolling update strategy for agent"
```

---

### Task 5: Update `.k8s/CLAUDE.md`

**Files:**

- Modify: `.k8s/CLAUDE.md`

- [ ] **Step 1: Add documentation for new config sections**

Add the following bullets to the Conventions list in `.k8s/CLAUDE.md`:

```markdown
- **Security contexts** on workspace (`serverK8sConfig`) and run
  (`runK8sConfig`) pods: `runAsNonRoot`, UID/GID 1234 (matches Dockerfile
  `teamster` user), `allowPrivilegeEscalation: false`, all capabilities dropped.
  `readOnlyRootFilesystem` intentionally omitted (dbt/Dagster write to `/tmp`).
- **`onlyAllowUserDefinedK8sConfigFields`** restricts what `dagster-cloud.yaml`
  and `dagster-k8s/config` tags can set: `resources`, `env`, `nodeSelector`,
  `affinity`, `annotations`, and `ttlSecondsAfterFinished`. Everything else is
  locked to Helm chart values.
- **Agent topology spread** uses `ScheduleAnyway` across
  `topology.kubernetes.io/zone` via `additionalPodSpecConfig`. Prefers
  cross-zone but allows same-zone during capacity exhaustion.
- **Agent readiness probe** checks for
  `/tmp/finished_initial_reconciliation_sentinel.txt`. Rolling update
  (`maxSurge: 200%`, `maxUnavailable: 0%`) ensures zero-downtime Helm upgrades.
```

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "docs(k8s): document security contexts, config restrictions, and agent resilience"
```

---

### Task 6: Dry-Run Verification and Deploy

**Files:**

- None modified — verification only

- [ ] **Step 1: Run Helm dry-run**

```bash
bash .k8s/dagster/install.sh
```

This script runs `helm repo update`, then `helm upgrade --dry-run` with the
override file. Review the rendered manifest for:

1. Agent pods have `topologySpreadConstraints` under pod spec
2. Agent pods have `readinessProbe` and `strategy` (rolling update)
3. Workspace pods have `securityContext` in the container spec
4. Run pods have `securityContext` in the container spec
5. `onlyAllowUserDefinedK8sConfigFields` is set (this is a Helm values key — it
   configures the agent's behavior, not a K8s manifest field, so it won't appear
   in rendered manifests but should be in the agent ConfigMap or equivalent)

When prompted "Dry-run succeeded. Apply to cluster? [y/N]", answer `y` only
after reviewing the dry-run output.

- [ ] **Step 2: Verify pods are healthy post-deploy**

```bash
kubectl -n dagster-cloud get pods -l app.kubernetes.io/name=dagster-cloud-agent -o wide
```

Confirm both agent replicas are Running in different zones. Check the topology:

```bash
kubectl -n dagster-cloud get pods -l app.kubernetes.io/name=dagster-cloud-agent \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.nodeName}{"\n"}{end}'
```

- [ ] **Step 3: Verify code server pods still schedule correctly**

After a code server redeploy (or wait for TTL rotation), confirm code servers
come up with the security context:

```bash
kubectl -n dagster-cloud get pods -l managed_by=K8sUserCodeLauncher -o wide
```

Pick one pod and verify security context:

```bash
kubectl -n dagster-cloud get pod <pod-name> \
  -o jsonpath='{.spec.containers[0].securityContext}' | python3 -m json.tool
```

Expected output should show `runAsNonRoot: true`, `runAsUser: 1234`,
`runAsGroup: 1234`, `allowPrivilegeEscalation: false`.
