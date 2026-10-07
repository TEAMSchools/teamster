# Code Server Scheduling Resilience, Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop code-server replacement pods from timing out during placement, so
a routine redeploy no longer leaves a code location in a terminal `ERROR` state
that only a human can clear.

**Architecture:** Three independent configuration changes, no new components.
Two land in the Helm values for the Dagster Cloud agent and take effect on a
manual `helm upgrade`; one lands in the five per-location `dagster-cloud.yaml`
files and ships through the normal deploy pipeline. Nothing in this phase
changes pod priority or the run-pod isolation.

**Tech Stack:** GKE Autopilot, Helm (`dagster-cloud` agent chart), Dagster+
hybrid agent, YAML.

Design spec:
`docs/superpowers/specs/2026-08-18-code-server-scheduling-resilience-design.md`.
Issue [#4907](https://github.com/TEAMSchools/teamster/issues/4907).

## Global Constraints

Every task's requirements implicitly include this section. Values are copied
verbatim from the spec.

- **The run-pod-to-code-server isolation stays hard.** Do not change
  `workspace.runK8sConfig.podSpecConfig.affinity.podAntiAffinity`. It remains
  `requiredDuringSchedulingIgnoredDuringExecution`. It was added after a real
  incident in which run pods starved and killed code servers, and `Evicted` has
  been 0 for all four measured weeks.
- **Code-server priority stays at 0.** Do not add `priorityClassName` to
  `workspace.serverK8sConfig`.
- `workspace.deploymentStartupTimeout` is set to `900`.
- The annotation value is exactly
  `cluster-autoscaler.kubernetes.io/safe-to-evict: "false"` — a quoted string,
  not a bare boolean.
- Code-server requests stay at `cpu: 500m` and `memory: 2.0Gi`. These meet the
  Autopilot extended-duration minimum of 500m / 2GiB, which
  `safe-to-evict: "false"` requires. Lowering either breaks the annotation.
- Code servers must not be moved to spot. `safe-to-evict: "false"` and
  `cloud.google.com/gke-spot` are mutually exclusive.
- All five `dagster-cloud.yaml` files change together. A partial change leaves
  locations behaving inconsistently for no reason.
- **Helm value changes require a manual `helm upgrade`** run by the user. `helm`
  and `kubectl` are not available to the agent in this environment, and
  `kubectl` is classifier-blocked. Every Helm verification step is handed to the
  user.
- Baseline to compare against, from the spec. Code-server pods only
  (`involvedObject.name` containing `-prod-`) in the `dagster-cloud` namespace:

  | Week         | Agent gRPC errors | Killing | ScaleDown | Preempted | Evicted | FailedScheduling |
  | ------------ | ----------------- | ------- | --------- | --------- | ------- | ---------------- |
  | Jul 20-27    | 85                | 122     | 42        | 21        | 0       | 472              |
  | Jul 28-Aug 4 | 134               | 197     | 59        | 37        | 0       | 454              |
  | Aug 4-11     | 106               | 118     | 48        | 22        | 0       | 213              |
  | Aug 11-18    | 100               | 142     | 38        | 32        | 0       | 438              |

## Worktree

All file paths below are relative to
`/workspaces/teamster/.worktrees/claude-code-server-scheduling` on branch
`cbini/fix/claude-code-server-scheduling`.

Use `git -C /workspaces/teamster/.worktrees/claude-code-server-scheduling` for
every git call. Run `trunk` as `/workspaces/teamster/.trunk/tools/trunk` with
the working directory set to the worktree — a relative invocation from the main
repo checks the main checkout's copies instead.

## File Structure

| File                                                          | Responsibility                                                                             | Delivery              |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------- |
| `.k8s/dagster/values-override.yaml`                           | agent + workspace Helm config: the deployment timeout and the code-server pod annotations  | manual `helm upgrade` |
| `src/teamster/code_locations/kippcamden/dagster-cloud.yaml`   | kippcamden per-location server affinity                                                    | normal deploy         |
| `src/teamster/code_locations/kippmiami/dagster-cloud.yaml`    | kippmiami per-location server affinity                                                     | normal deploy         |
| `src/teamster/code_locations/kippnewark/dagster-cloud.yaml`   | kippnewark per-location server affinity                                                    | normal deploy         |
| `src/teamster/code_locations/kipppaterson/dagster-cloud.yaml` | kipppaterson per-location server affinity                                                  | normal deploy         |
| `src/teamster/code_locations/kipptaf/dagster-cloud.yaml`      | kipptaf per-location server affinity                                                       | normal deploy         |
| `.k8s/CLAUDE.md`                                              | operational reference: which timeout governs what, pre-warming, and the no-retry behaviour | docs                  |

`.k8s/dagster/values.yaml` is auto-downloaded from Helm and must never be
edited.

## Tasks

### Task 1: Helm workspace timeout and code-server eviction protection

Both changes live in one file and take effect together on a single
`helm upgrade`, so they are one task — there is no state in which one is applied
and the other is not.

**Files:**

- Modify: `.k8s/dagster/values-override.yaml` (the `workspace` block, currently
  starting at line 96)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: nothing later tasks depend on. Task 4 verifies the effect of this
  task and Task 2 together.

- [ ] **Step 1: Confirm the chart exposes the key and the current value is the
      default**

Run:

```bash
grep -n -B4 'deploymentStartupTimeout' /workspaces/teamster/.k8s/dagster/values.yaml
grep -n 'deploymentStartupTimeout\|serverProcessStartupTimeout' \
  /workspaces/teamster/.worktrees/claude-code-server-scheduling/.k8s/dagster/values-override.yaml
```

Expected: `values.yaml` documents `deploymentStartupTimeout: ~` with the comment
"If not set, defaults to 300 seconds." The override file contains
`serverProcessStartupTimeout: 300` and **no** `deploymentStartupTimeout` line.
That absence is the defect — the governing timeout has never been set.

If `deploymentStartupTimeout` already appears in the override file, stop:
someone has changed this since the spec was written, and the plan needs
revisiting.

- [ ] **Step 2: Add the deployment timeout**

In `.k8s/dagster/values-override.yaml`, replace:

```yaml
workspace:
  serverProcessStartupTimeout: 300
```

with:

```yaml
workspace:
  # Time the agent waits for a code server DEPLOYMENT to become ready -- in
  # practice, for the pod to be scheduled. Distinct from
  # serverProcessStartupTimeout below, which only starts once the Deployment
  # exists. The chart default is 300s, which sits inside the 3-9 minute NAP
  # FailedScheduling window documented in CLAUDE.md, so an ordinary provisioning
  # wait times out. On timeout the agent uploads an error, the control plane
  # records the location as ERROR, and _should_trigger_recovery then refuses to
  # retry ("control plane agrees there is an error") -- the location stays dead
  # until a push or a manual redeploy.
  deploymentStartupTimeout: 900

  serverProcessStartupTimeout: 300
```

- [ ] **Step 3: Add the eviction-protection annotation**

In the same file, in `workspace.serverK8sConfig.podTemplateSpecMetadata`
(currently line 131), replace:

```yaml
podTemplateSpecMetadata: # raw config for the pod's metadata
  annotations:
    operator.1password.io/auto-restart: "true"
```

with:

```yaml
podTemplateSpecMetadata: # raw config for the pod's metadata
  annotations:
    operator.1password.io/auto-restart: "true"
    # Code servers were the only pod type without this -- the agent
    # (dagsterCloudAgent.annotations) and run pods
    # (runK8sConfig.podTemplateSpecMetadata) both carry it. Blocks
    # cluster-autoscaler eviction, which accounted for 38-59 code-server
    # relocations per week. Compatible here: requests above are 500m/2.0Gi,
    # meeting the Autopilot extended-duration minimum, and code servers are
    # not on spot (the two are mutually exclusive). Note extended-duration
    # protection expires after 7 days, which is far longer than the interval
    # between deploys.
    cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
```

- [ ] **Step 4: Verify the file still parses and the constraints hold**

Run:

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && uv run python -c "
import yaml
d = yaml.safe_load(open('.k8s/dagster/values-override.yaml'))
w = d['workspace']
assert w['deploymentStartupTimeout'] == 900, w.get('deploymentStartupTimeout')
assert w['serverProcessStartupTimeout'] == 300
ann = w['serverK8sConfig']['podTemplateSpecMetadata']['annotations']
assert ann['cluster-autoscaler.kubernetes.io/safe-to-evict'] == 'false', ann
assert ann['operator.1password.io/auto-restart'] == 'true', ann
req = w['serverK8sConfig']['containerConfig']['resources']['requests']
assert req['cpu'] == '500m' and req['memory'] == '2.0Gi', req
run_aff = w['runK8sConfig']['podSpecConfig']['affinity']['podAntiAffinity']
assert 'requiredDuringSchedulingIgnoredDuringExecution' in run_aff, 'run-pod isolation must stay required'
assert 'priorityClassName' not in w['serverK8sConfig'].get('podSpecConfig', {}), 'code-server priority must stay 0'
print('OK: timeout 900, safe-to-evict false as string, requests unchanged, isolation intact, no priority class')
"
```

Expected: `OK: ...`. The `safe-to-evict` assertion compares against the
**string** `'false'`; if it fails with `False`, the value was written as a bare
YAML boolean and must be quoted.

- [ ] **Step 5: Lint**

Run:

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  .k8s/dagster/values-override.yaml </dev/null
```

Expected: `No issues`, or only `unformatted file` from prettier, which the
pre-commit `fmt` hook fixes. Any `yamllint` finding naming a rule must be fixed
before committing.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && \
git add .k8s/dagster/values-override.yaml && \
git commit -m "fix(k8s): set deploymentStartupTimeout and protect code servers from autoscaler eviction

deploymentStartupTimeout was never set, so it sat at the chart default of 300s
while .k8s/CLAUDE.md documents NAP FailedScheduling waits of 3 to 9 minutes. An
ordinary provisioning wait therefore times out, and the resulting error is
terminal: once the control plane records the location as ERROR,
_should_trigger_recovery refuses to retry it.

Code servers were also the only pod type with no safe-to-evict annotation; the
agent and run pods both carry it. That accounted for 38 to 59 autoscaler
relocations per week.

Neither change touches pod priority or the run-pod isolation.

Refs #4907"
```

### Task 2: Relax the per-location self-anti-affinity to preferred

**Files:**

- Modify: `src/teamster/code_locations/kippcamden/dagster-cloud.yaml:21-32`
- Modify: `src/teamster/code_locations/kippmiami/dagster-cloud.yaml:21-32`
- Modify: `src/teamster/code_locations/kippnewark/dagster-cloud.yaml:21-32`
- Modify: `src/teamster/code_locations/kipppaterson/dagster-cloud.yaml:21-32`
- Modify: `src/teamster/code_locations/kipptaf/dagster-cloud.yaml:34-45`

**Interfaces:**

- Consumes: nothing from Task 1. This task is independently landable.
- Produces: nothing later tasks import. Task 4 measures its effect.

**Superseded in part.** The YAML-key assertion in Step 3 below is weaker than
this note claims: it would pass on `podAffinityTerms` (plural) or a stray
`weight` inside `podAffinityTerm`. `tests/test_k8s_config.py` now runs the
agent's own coercion (`k8s_model_from_dict(V1PodSpec, ...)`), which rejects
both, and includes a negative case proving it is not vacuous. Prefer that check
for Phases 2 and 3.

**Critical structural note.** `preferred` is not a rename of `required`. The
required form takes a list of `PodAffinityTerm` directly; the preferred form
takes a list of `WeightedPodAffinityTerm`, where each entry is `weight` plus a
nested `podAffinityTerm`. Renaming the key without adding that wrapper produces
config the agent rejects at deploy time. Use `weight: 100`, the maximum, so the
scheduler still prefers separation as strongly as it can while no longer
treating it as a hard requirement.

- [ ] **Step 1: Confirm all five files currently hold the required form**

Run:

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && \
grep -c 'requiredDuringSchedulingIgnoredDuringExecution' \
  src/teamster/code_locations/*/dagster-cloud.yaml
```

Expected: exactly `1` for each of the five files. If any file reports `0`, it
has already been changed; if any reports `2` or more, it has additional affinity
rules this plan does not account for and you should stop and re-read the file.

- [ ] **Step 2: Rewrite the affinity block in each of the five files**

For each location, replace the `server_k8s_config.pod_spec_config.affinity`
block. Shown for `kippcamden`; repeat for `kippmiami`, `kippnewark`,
`kipppaterson`, and `kipptaf`, substituting the location name in `values`. Do
not copy kippcamden's name into the other four files.

Replace:

```yaml
server_k8s_config:
  pod_spec_config:
    affinity:
      podAntiAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
                - key: location_name
                  operator: In
                  values:
                    - kippcamden
            topologyKey: kubernetes.io/hostname
```

with:

```yaml
server_k8s_config:
  pod_spec_config:
    affinity:
      podAntiAffinity:
        # Preferred, not required. With one replica per location this
        # spreads nothing; as `required` its only live effect was
        # forbidding the replacement pod from the outgoing pod's node
        # during a rollover -- the one node guaranteed to have arm64
        # Scale-Out capacity sized for a code server and, by the run-pod
        # anti-affinity, no run pods on it. That forced NAP to build a new
        # node on every redeploy. Cross-location spreading is handled
        # separately by topologySpreadConstraints in the Helm values.
        preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                  - key: location_name
                    operator: In
                    values:
                      - kippcamden
              topologyKey: kubernetes.io/hostname
```

- [ ] **Step 3: Verify all five files parse and match the
      WeightedPodAffinityTerm shape**

Run:

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && uv run python -c "
import pathlib, yaml
locs = ['kippcamden', 'kippmiami', 'kippnewark', 'kipppaterson', 'kipptaf']
for loc in locs:
    p = pathlib.Path(f'src/teamster/code_locations/{loc}/dagster-cloud.yaml')
    d = yaml.safe_load(p.read_text())
    loc_cfg = d['locations'][0]
    aff = loc_cfg['container_context']['k8s']['server_k8s_config']['pod_spec_config']['affinity']
    anti = aff['podAntiAffinity']
    assert 'requiredDuringSchedulingIgnoredDuringExecution' not in anti, f'{loc} still required'
    terms = anti['preferredDuringSchedulingIgnoredDuringExecution']
    assert len(terms) == 1, f'{loc}: {len(terms)} terms'
    t = terms[0]
    assert t['weight'] == 100, f'{loc}: weight is not 100'
    pat = t['podAffinityTerm']
    assert pat['topologyKey'] == 'kubernetes.io/hostname', f'{loc} topologyKey'
    vals = pat['labelSelector']['matchExpressions'][0]['values']
    assert vals == [loc], f'{loc} selects {vals}'
    print(f'{loc}: OK')
"
```

Expected: five `OK` lines. The `vals == [loc]` assertion is what catches a
copy-paste that left `kippcamden` in another location's file — the most likely
error in this task.

If the `d['locations'][0]['container_context']['k8s']` path raises `KeyError`,
print the parsed structure and adjust the accessor; the assertion targets are
the values, not the path.

- [ ] **Step 4: Confirm the run-pod isolation was not touched**

Run:

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && uv run python -c "
import yaml
d = yaml.safe_load(open('.k8s/dagster/values-override.yaml'))
anti = d['workspace']['runK8sConfig']['podSpecConfig']['affinity']['podAntiAffinity']
assert 'requiredDuringSchedulingIgnoredDuringExecution' in anti, 'run-pod isolation lost'
assert 'preferredDuringSchedulingIgnoredDuringExecution' not in anti, 'run-pod isolation weakened'
terms = anti['requiredDuringSchedulingIgnoredDuringExecution']
assert len(terms) == 2, f'expected 2 run-pod anti-affinity terms, found {len(terms)}'
print('OK: run-pod isolation still required, both terms intact')
"
```

Expected: `OK: run-pod isolation still required, both terms intact`. This reads
the committed file rather than a diff, so it cannot pass vacuously. The two
terms are the code-server selector and the agent selector; losing either would
silently undo the isolation this phase promises to preserve.

- [ ] **Step 5: Lint all five files**

Run:

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/teamster/code_locations/kippcamden/dagster-cloud.yaml \
  src/teamster/code_locations/kippmiami/dagster-cloud.yaml \
  src/teamster/code_locations/kippnewark/dagster-cloud.yaml \
  src/teamster/code_locations/kipppaterson/dagster-cloud.yaml \
  src/teamster/code_locations/kipptaf/dagster-cloud.yaml </dev/null
```

Expected: `No issues`, or only prettier `unformatted file`. This check takes
over two minutes across five files, so run it in the background and read the
output file only after it exits — its progress spinner emits no result lines, so
grepping partial output reads as a false clean.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && \
git add src/teamster/code_locations/kippcamden/dagster-cloud.yaml \
        src/teamster/code_locations/kippmiami/dagster-cloud.yaml \
        src/teamster/code_locations/kippnewark/dagster-cloud.yaml \
        src/teamster/code_locations/kipppaterson/dagster-cloud.yaml \
        src/teamster/code_locations/kipptaf/dagster-cloud.yaml && \
git commit -m "fix(k8s): relax per-location code server self-anti-affinity to preferred

With one replica per location the required form spreads nothing. Its only live
effect was forbidding the replacement pod from the outgoing pod's node during a
rollover -- the one node guaranteed to have arm64 Scale-Out capacity sized for a
code server and, by the run-pod anti-affinity, no run pods on it. That forced NAP
to provision a new node on every redeploy, which is what pushes placement past
the startup timeout.

Cross-location spreading is unaffected; it comes from topologySpreadConstraints
in the Helm values, not from this rule.

Preferred takes WeightedPodAffinityTerm rather than PodAffinityTerm, so the term
is nested under podAffinityTerm with weight 100.

The run-pod-to-code-server isolation is unchanged and stays required.

Refs #4907"
```

### Task 3: Correct the operational documentation

**Files:**

- Modify: `.k8s/CLAUDE.md` — the "Timeout types (do not conflate)" bullet in
  Troubleshooting, the "Autopilot node pre-warming" bullet in Troubleshooting,
  and the "Agent Error Observability" section

**Interfaces:**

- Consumes: nothing.
- Produces: nothing.

This task exists because the documentation gap actively caused a wrong
diagnosis: the "Timeout types" bullet documents only
`serverProcessStartupTimeout`, which led to identifying the wrong knob during
the investigation behind this plan.

- [ ] **Step 1: Replace the timeout-types bullet**

In `.k8s/CLAUDE.md`, find the bullet beginning
`- **Timeout types** (do not conflate):` and replace that whole bullet with:

```markdown
- **Timeout types** (do not conflate). Three distinct waits, in the order they
  occur:
  1. **Deployment startup** (`deploymentStartupTimeout`, Helm `workspace` key,
     chart default 300s, set to 900s) — agent waits for the code server
     Deployment to become ready, i.e. for the pod to be SCHEDULED. This is the
     one that fires during a NAP `FailedScheduling` wait, and its failure
     message is `Timed out waiting for deployment <name>` with
     `Pod status: Pending`. Governs `wait_for_deployment_complete`, not
     `_wait_for_dagster_server_process`.
  1. **Server process startup** (`serverProcessStartupTimeout`, Helm `workspace`
     key, default 180s, set to 300s) — agent waits for a gRPC ping AFTER the
     Deployment exists. Fires when Dagster definitions are slow to import, not
     when the pod cannot be placed.
  1. **Sensor execution** (300s, Dagster+ deployment setting) — sensor ran too
     long; the code server stays up and no churn results.
```

- [ ] **Step 2: Replace the pre-warming bullet**

Find the bullet beginning `- **Autopilot node pre-warming**: Not possible` and
replace that whole bullet with:

```markdown
- **Autopilot node pre-warming**: no node-lifecycle control — no DaemonSets, no
  image pre-pulling, no cordon that holds. But capacity CAN be reserved at the
  workload layer with balloon pods: a Deployment of placeholder pods on a
  negative `PriorityClass` holds nodes that real pods preempt instantly, and the
  displaced placeholder then triggers NAP to re-warm the buffer. Google
  documents this for Autopilot. Not currently deployed here; see
  `docs/superpowers/specs/2026-08-18-code-server-scheduling-resilience-design.md`
  Phase 2, which is gated on verifying Warden admits a negative priority value.
```

- [ ] **Step 3: Document the no-retry behaviour**

In the "Agent Error Observability" section, append this bullet after the
existing "Hybrid daemon location" bullet:

```markdown
- **A timed-out code server deployment is TERMINAL — the agent never retries
  it.** `_should_trigger_recovery` in
  `dagster_cloud/workspace/user_code_launcher/user_code_launcher.py` returns
  `False` when the location is in `control_plane_error_locations` ("control
  plane agrees there is an error, don't retry"). Recovery fires only when the
  agent holds a local error while the control plane thinks the location is
  healthy. Normal reconciliation redeploys only when
  `actual_entry.update_timestamp != desired_entry.update_timestamp`, which
  changes on a new deploy, and the periodic health check needs a running
  endpoint a never-started pod does not have. So a location that fails to
  schedule stays `ERROR` until someone pushes a commit or clicks redeploy. No
  agent setting changes this;
  `DAGSTER_CLOUD_DISABLE_LOCAL_ERROR_SERVER_RECOVERY` only turns recovery off.
```

- [ ] **Step 4: Lint the documentation**

Run:

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .k8s/CLAUDE.md </dev/null
```

Expected: `No issues`, or only prettier `unformatted file`. Watch specifically
for markdownlint `MD029` on the numbered list added in Step 1 — every item must
be `1.`, because `trunk fmt` renumbers sequentially and a nested list under a
bullet restarts numbering.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && \
git add .k8s/CLAUDE.md && \
git commit -m "docs(k8s): distinguish the three startup timeouts, correct pre-warming, record no-retry

The Timeout types bullet documented only serverProcessStartupTimeout and omitted
deploymentStartupTimeout entirely, which is the timeout that actually fires during
a NAP FailedScheduling wait. That gap caused a wrong diagnosis during the
investigation behind #4907.

Also corrects the claim that Autopilot pre-warming is impossible -- true of
DaemonSets and image pre-pulling, but balloon pods are a documented workload-layer
option -- and records that a timed-out code server deployment is terminal, since
that is the operational consequence and it was nowhere in the repo.

Refs #4907"
```

### Task 4: Deploy, activate, and verify

This task is split between the agent and the user because the agent cannot run
`helm` or `kubectl` in this environment.

**Files:** none modified.

**Interfaces:**

- Consumes: Tasks 1, 2, and 3, all committed.

- [ ] **Step 1: Push and open the pull request**

```bash
cd /workspaces/teamster/.worktrees/claude-code-server-scheduling && git push
```

Then open a PR using `.github/pull_request_template.md`, with `Refs #4907` in
the body. Note in Reviewer Notes that the Helm half requires a manual
`helm upgrade` and does not take effect on merge.

- [ ] **Step 2: Confirm CI is green on both surfaces**

A PR's CI lives on two disjoint surfaces. Check both:

```bash
gh pr checks <PR_NUMBER> --json name,bucket
```

Expected: every entry `pass` or `skipping`. `dagster-cloud-deploy / deploy`
emits one same-named check-run per code location, roughly five, so wait for all
of them to reach a terminal state. `mergeable_state: blocked` with everything
green means the change is waiting on a CODEOWNERS approval, not on CI.

- [ ] **Step 3: After merge, confirm all five locations reloaded**

The `dagster-cloud.yaml` change from Task 2 ships on merge. Confirm each
location actually picked it up rather than assuming a green deploy job means it
did:

```text
Call mcp__dagster__get_location_load_history for each of kipptaf, kippnewark,
kippcamden, kippmiami, kipppaterson with limit=3. For each location the newest
entry must read loadStatus LOADED with a commit_hash matching the merge commit.
```

Expected: five locations, newest entry `LOADED`, matching commit hash. A green
Actions deploy job is not evidence the agent reloaded.

- [ ] **Step 4: USER ACTION — run the Helm upgrade**

The Task 1 changes do nothing until this runs. Hand the user:

```bash
cd /workspaces/teamster && bash .k8s/dagster/install.sh
```

If `helm: command not found` or the cluster is unreachable, `.k8s/setup.sh` has
not been run in this shell; run that first. `install.sh` is deploy-only and must
not have bootstrap logic added to it.

- [ ] **Step 5: USER ACTION — confirm the new timeout is live**

```bash
kubectl -n dagster-cloud get configmap \
  -l app.kubernetes.io/name=dagster-cloud-agent -o yaml \
  | grep -i -B3 -A3 'startup_timeout'
```

Expected: the agent's rendered config shows a deployment startup timeout of 900.
If only the server-process timeout appears, the override did not reach the
rendered config and Task 1 Step 2 should be re-checked before going further.

- [ ] **Step 6: USER ACTION — confirm the annotation lands on new code server
      pods**

The annotation applies to pods created after the upgrade; existing code servers
keep the old spec until they are recycled.

```bash
kubectl -n dagster-cloud get pods -l managed_by=K8sUserCodeLauncher \
  -o custom-columns='NAME:.metadata.name,SAFE_TO_EVICT:.metadata.annotations.cluster-autoscaler\.kubernetes\.io/safe-to-evict'
```

Expected: `false` for every code-server pod created after the upgrade. Pods
still showing `<none>` predate it and will pick it up on their next rollover.

- [ ] **Step 7: Measure against the baseline after one week**

Re-run the same six counters over a full week and compare with the Global
Constraints table. Query shapes, against project `teamster-332318`:

Agent gRPC failures:

```text
resource.type="k8s_container"
resource.labels.namespace_name="dagster-cloud"
resource.labels.pod_name:"user-cloud-dagster-cloud-agent"
textPayload:"Could not reach user code server"
```

Code-server disruptions, run once per reason substituting `Preempted`,
`ScaleDown`, `Killing`, `Evicted`, `FailedScheduling`:

```text
resource.type="k8s_pod"
resource.labels.namespace_name="dagster-cloud"
logName:"events"
jsonPayload.involvedObject.name:"-prod-"
jsonPayload.reason="REASON"
```

These queries return well over 100 entries per week, so paginate: when a query
returns exactly 100, re-run it with the start time advanced to the last returned
timestamp rounded up to the next whole second, and sum. Use
`format="{{.timestamp}}"` to keep the output small.

Success criteria, from the spec:

- Zero `loadStatus: ERROR` entries carrying the
  `Timed out waiting for deployment` signature in any location's load history.
- `FailedScheduling` on code-server pods materially below the 213 to 472 band.
- Agent gRPC errors below the 85 to 134 per week band.
- `Evicted` still 0, which is the check that the isolation was not weakened.

- [ ] **Step 8: Record the result on the issue**

Post the measured week as a comment on
[#4907](https://github.com/TEAMSchools/teamster/issues/4907) next to the
baseline table, and state plainly whether Phases 2 and 3 are still warranted at
the originally proposed scale. If `FailedScheduling` collapsed and no terminal
failures occurred, Phase 2's continuous cost may no longer be justified and
Phase 3 may be the only remaining gap. Do not open the Phase 2 or Phase 3 plans
before this measurement exists.

## Notes for the implementer

- Do not run `trunk fmt` or `trunk check` outside the steps that call for it.
  The `trunk-fmt-pre-commit` hook formats at commit time and
  `trunk-check-pre-push` gates the push.
- A `--force` check over five files takes more than two minutes. Background it
  and read the output only after it exits.
- The `trunk` binary lives only in the main repo; `.trunk/tools/` is gitignored
  and absent from the worktree. If `/workspaces/teamster/.trunk/tools/trunk`
  does not exist on a cold Codespace, use `~/.cache/trunk/launcher/trunk`, which
  is always present and creates the symlink on first run.
- Editing files under the worktree path re-injects that worktree's CLAUDE.md
  files into context on every call. For a multi-file pass like Task 2, either
  delegate the edits to subagents or apply them with a script written to
  `.claude/scratch/` and run by absolute path from the main repo.
- Nothing in this phase may add a `priorityClassName` to `serverK8sConfig` or
  weaken `runK8sConfig`'s anti-affinity. If a step seems to require either, stop
  and re-read the Global Constraints.
