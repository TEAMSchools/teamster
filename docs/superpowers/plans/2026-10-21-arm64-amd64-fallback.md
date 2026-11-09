# arm64-first, amd64-fallback ComputeClass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run, step, and code server pods prefer arm64 nodes and fall back to
amd64 automatically when GKE runs out of arm64 capacity.

**Architecture:** One custom GKE ComputeClass, `dagster-arm-first`, with
`podFamily` priorities, ships through the Helm chart's `extraManifests`. Code
server and run pod `nodeSelector`s point at it instead of built-in Scale-Out
arm64, and carry an explicit arm64 toleration. The agent does not change.

**Tech Stack:** Helm values (`.k8s/dagster/values-override.yaml`), pytest
structural checks (`tests/test_k8s_config.py`), GKE Autopilot.

**Spec:** `docs/superpowers/specs/2026-10-21-arm64-amd64-fallback-design.md`

## Global Constraints

- ComputeClass name: `dagster-arm-first`.
- Priorities, in order: `podFamily: general-purpose-arm`, then
  `podFamily: general-purpose`. `spec.autopilot.enabled: true`.
- Code server and run pod `nodeSelector` is exactly
  `cloud.google.com/compute-class: dagster-arm-first`. No `kubernetes.io/arch`
  key.
- Toleration on both:
  `{key: kubernetes.io/arch, operator: Equal, value: arm64, effect: NoSchedule}`.
- Unchanged: the agent's Scale-Out amd64 pin, all `safe-to-evict: "false"`
  annotations, resources, `podFailurePolicy`, anti-affinity, topology spread,
  priority 0.
- No node affinity on code server or run pods. Warden rejects it alongside
  `safe-to-evict` on a custom class.
- Run tests with `uv run pytest tests/test_k8s_config.py`, never bare `pytest`.
- `kubectl` and `helm` are run by the user in their terminal, not by Claude.

## Review Focus

1. A per-location `dagster-cloud.yaml` that sets `nodeSelector` or node affinity
   would override or break the class. Expected: none do. Pinned in Task 1.
2. The agent accidentally moved to the new class. Its image is amd64-only.
   Pinned in Task 1.
3. A missing arm64 toleration makes every pod silently land on amd64. Pinned in
   Task 1. The post-deploy check in Task 3 catches it live.
4. The fallback is slower than the 600-second run start timeout. Gate in Task 3.
5. The ComputeClass fails to render or apply through `extraManifests`, because
   it is cluster-scoped. Caught by the `install.sh` dry-run in Task 3.

---

### Task 1: ComputeClass and pod placement

**Files:**

- Modify: `.k8s/dagster/values-override.yaml`:
  - code server `podSpecConfig` (about lines 186–193)
  - run `podSpecConfig` (about lines 262–281)
  - `extraManifests` (line 331 onward)
- Test: `tests/test_k8s_config.py`

**Interfaces:**

- Produces: the ComputeClass named `dagster-arm-first` in `extraManifests`. Task
  2's docs and Task 3's checks refer to that name.

- [ ] **Step 1: Write the failing tests** in `tests/test_k8s_config.py`,
      following the file's existing style (`_helm_values()`, docstrings that
      give the why).

```python
ARM_TOLERATION = {
    "key": "kubernetes.io/arch",
    "operator": "Equal",
    "value": "arm64",
    "effect": "NoSchedule",
}


def test_compute_class_prefers_arm_then_falls_back_to_amd64():
    (compute_class,) = [
        m for m in _helm_values()["extraManifests"] if m["kind"] == "ComputeClass"
    ]

    assert compute_class["metadata"]["name"] == "dagster-arm-first"
    assert compute_class["spec"]["autopilot"]["enabled"] is True
    assert compute_class["spec"]["priorities"] == [
        {"podFamily": "general-purpose-arm"},
        {"podFamily": "general-purpose"},
    ]


@pytest.mark.parametrize("config", ["serverK8sConfig", "runK8sConfig"])
def test_dagster_pods_select_the_arm_first_class(config: str):
    pod_spec = _helm_values()["workspace"][config]["podSpecConfig"]

    assert pod_spec["nodeSelector"] == {
        "cloud.google.com/compute-class": "dagster-arm-first"
    }
    assert ARM_TOLERATION in pod_spec["tolerations"]
    assert "nodeAffinity" not in pod_spec.get("affinity", {})


@pytest.mark.parametrize("location", CODE_LOCATIONS)
def test_locations_do_not_override_placement(location: str):
    pod_spec = _server_pod_spec_config(location)

    assert "nodeSelector" not in pod_spec
    assert "nodeAffinity" not in pod_spec.get("affinity", {})


def test_agent_stays_on_scale_out_amd64():
    assert _helm_values()["dagsterCloudAgent"]["nodeSelector"] == {
        "cloud.google.com/compute-class": "Scale-Out",
        "kubernetes.io/arch": "amd64",
    }
```

Docstrings carry the why from the spec:

- Fallback: arm64 stockouts fail runs at the start timeout.
- Toleration: without it, pods can never land on arm64.
- No node affinity: Warden rejects it next to `safe-to-evict`.
- Agent: its image is amd64-only.

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run pytest tests/test_k8s_config.py -k "compute_class or arm_first or override_placement or agent_stays" -v 2>&1 | tail -n 20`

Expected: the `compute_class` and `arm_first` tests FAIL. The
`override_placement` and `agent_stays` tests PASS already, because they guard
the current state.

- [ ] **Step 3: Edit `values-override.yaml`.**
  - Append the ComputeClass manifest from the spec to `extraManifests`.
  - On both `podSpecConfig` blocks, replace the two-key `nodeSelector` with the
    class selector and add `tolerations: [ARM_TOLERATION]`.
  - Rewrite the "Hard-pin to built-in Scale-Out arm64 (T2A) ... No fallback"
    comments above each block to say:
    - pods prefer arm64 and fall back to amd64 through `dagster-arm-first`;
    - the toleration is why they can land on arm64;
    - node affinity must not be added (Warden).

  Follow `.claude/rules/comments.md`: keep the why, drop dates and history.

- [ ] **Step 4: Rename `test_code_server_requests_meet_scale_out_minimum`** to
      `test_code_server_requests_meet_extended_duration_minimum`.
  - Reword its docstring and the `CODE_SERVER_MIN_*` comment (line 25):
    Autopilot applies the extended-duration minimum to `safe-to-evict` pods.
  - Do not change the values.

- [ ] **Step 5: Run the whole file to verify it passes**

Run: `uv run pytest tests/test_k8s_config.py -v 2>&1 | tail -n 30`

Expected: all PASS.

- [ ] **Step 6: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .k8s/dagster/values-override.yaml tests/test_k8s_config.py </dev/null
git add .k8s/dagster/values-override.yaml tests/test_k8s_config.py
git commit -m "feat(k8s): prefer arm64 and fall back to amd64 via ComputeClass"
```

### Task 2: Update the rules that forbid this

**Files:**

- Modify: `.k8s/CLAUDE.md` _Scheduling_ (lines 56–69)
- Modify: `.claude/skills/dagster-k8s-ops/SKILL.md` (line 76)

Open both with the Read tool, not `cat`. Follow
`.claude/rules/claude-md-editing.md`.

- [ ] **Step 1: Edit `.k8s/CLAUDE.md`.**
  - Replace the "Built-in `Scale-Out` only — do NOT use Custom ComputeClasses"
    bullet. Use a `podFamily` class only: it is billed per pod and honors
    `safe-to-evict` against autoscaler scale-down. Machine-family custom classes
    are still billed per VM, so do not use them.
  - Replace "Pod placement" and "No fallback": code server and run pods use
    `dagster-arm-first` (arm64 first, amd64 fallback); the agent stays on
    Scale-Out amd64.
  - Add: no node affinity on these pods. Warden rejects it next to
    `safe-to-evict` on a custom class.
  - Add: custom-class pods get no extended run time, so weekend maintenance
    drains can restart code servers.
  - `rg` "T2A", "arm64", and "ComputeClass" across `CLAUDE.md` files,
    `.claude/`, and `docs/guides/`. Fix any other restatement.

- [ ] **Step 2: Edit `SKILL.md` line 76:** "the others to arm64" becomes "the
      others to the `dagster-arm-first` class, a different node pool".

- [ ] **Step 3: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .k8s/CLAUDE.md .claude/skills/dagster-k8s-ops/SKILL.md </dev/null
git add .k8s/CLAUDE.md .claude/skills/dagster-k8s-ops/SKILL.md
git commit -m "docs(k8s): allow podFamily ComputeClass for arm64 fallback"
```

### Task 3: Gate and rollout (user runs `kubectl` and `helm`)

Claude prepares the files and commands. The user runs them and pastes the
output.

- [ ] **Step 1: Forced-fallback timing test (merge gate).**
  - Claude writes a throwaway manifest in the session scratchpad:
    - namespace `computeclass-fallback-test`;
    - class `dagster-fallback-test`, whose first priority cannot be provisioned
      in `us-central1`, followed by `podFamily: general-purpose`;
    - one Job pod shaped like a run pod (500m / 2Gi, `safe-to-evict`, the arm64
      toleration).
  - The user applies it and reports the time from Job creation to `Running`,
    plus the node's `kubernetes.io/arch`.
  - Pass: the pod lands on amd64 well under 600 seconds.
  - Over or near 600 seconds: stop and return to the user (see the spec's
    _Fallback speed_).
  - Then the user deletes the test namespace and class.

- [ ] **Step 2: Open the PR** from the branch, with body `Closes #6065`. Record
      the Step 1 timing in the PR body.

- [ ] **Step 3: After merge, the user deploys.**
  - Run `bash .k8s/dagster/install.sh`. The dry-run must succeed before the user
    applies.
  - Then check:
    - `kubectl get computeclass dagster-arm-first` exists;
    - the next run pod has `cloud.google.com/compute-class: dagster-arm-first`;
    - that pod's node is `kubernetes.io/arch=arm64`.
