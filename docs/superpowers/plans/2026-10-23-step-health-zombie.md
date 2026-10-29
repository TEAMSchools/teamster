# Fail Fast on Zombie Step Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A step whose Kubernetes Job completed more than 60 s ago, while the
run pod still treats the step as running, is reported unhealthy so the step
fails and the run's auto-retry takes over.

**Architecture:** A `K8sStepHandler` subclass adds one rule after upstream's
`check_step_health`. An executor definition wraps `k8s_job_executor`: it builds
the stock `StepDelegatingExecutor` and swaps its handler's class for the
subclass. All 5 code locations use the wrapper.

**Tech Stack:** Python 3.13, `dagster`, `dagster-k8s` 0.29.26, `kubernetes`
client models, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-step-health-zombie-design.md`

## Global Constraints

- Grace period: 60 s, one module constant.
- No upstream init code copied from `dagster_k8s/executor.py`.
- The wrapper keeps `k8s_job_executor`'s name (`"k8s"`), config schema, and
  requirements unchanged.
- Upstream's unhealthy results (Job missing, Job failed) pass through unchanged.
- Unhealthy reason contains the stable substring
  `completed without a step result` (the day-2 classifier matches it).
- Run tests with `uv run pytest tests/test_dagster_executors.py` only; never
  bare `uv run pytest`.

## Review Focus

- Job status with `succeeded` set but `completion_time` `None` → healthy (no
  crash). Test in Task 1.
- `completion_time` is timezone-aware UTC from the k8s client; compare against
  an aware `datetime.now(UTC)`, never naive. Test in Task 1 uses aware values.
- Upstream raises from `get_job_status` (API error) → exception propagates
  unchanged; `StepDelegatingExecutor` already catches and logs it. Test in
  Task 1.
- The wrapped executor exposes the same config schema as the stock one, so
  existing executor run config still validates. Test in Task 2.
- The swap must reach the handler the executor actually calls (`_step_handler`);
  a dagster-k8s upgrade that renames it must fail a test, not silently skip the
  fix. Test in Task 2.

---

### Task 1: Zombie-aware step handler

**Files:**

- Create: `src/teamster/core/executors.py`
- Test: `tests/test_dagster_executors.py`

**Interfaces:**

- Produces: `class ZombieAwareK8sStepHandler(K8sStepHandler)` with
  `check_step_health(self, step_handler_context: StepHandlerContext) -> CheckStepHealthResult`;
  module constant `ZOMBIE_JOB_GRACE_SECONDS = 60`.

- [ ] **Step 1: Write the failing tests**

Build the handler without its `__init__` (it loads kube config):
`handler = object.__new__(ZombieAwareK8sStepHandler)`, then set
`handler._api_client = Mock()` and patch the instance's `_get_step_key`,
`_get_k8s_step_job_name`, `_get_container_context` to return `"my_step"`,
`"dagster-step-abc"`, and `SimpleNamespace(namespace="dagster-cloud")`. Status
objects are `kubernetes.client.V1JobStatus`. Tests:

```python
def test_succeeded_past_grace_is_unhealthy():
    # succeeded=1, completion_time = now(UTC) - 61 s
    result = handler.check_step_health(ctx)
    assert not result.is_healthy
    assert "completed without a step result" in result.unhealthy_reason
    assert "dagster-step-abc" in result.unhealthy_reason

def test_succeeded_inside_grace_is_healthy():
    # succeeded=1, completion_time = now(UTC) - 30 s
    assert handler.check_step_health(ctx).is_healthy

def test_succeeded_without_completion_time_is_healthy():
    # succeeded=1, completion_time=None
    assert handler.check_step_health(ctx).is_healthy

def test_running_job_is_healthy():
    # active=1, succeeded=None, completion_time=None
    assert handler.check_step_health(ctx).is_healthy

def test_failed_job_keeps_upstream_reason():
    # failed=1
    result = handler.check_step_health(ctx)
    assert not result.is_healthy
    assert result.unhealthy_reason.startswith("Discovered failed Kubernetes job")

def test_missing_job_keeps_upstream_reason():
    # get_job_status returns None
    result = handler.check_step_health(ctx)
    assert "could not be found" in result.unhealthy_reason

def test_status_api_error_propagates():
    # get_job_status raises ApiException
    with pytest.raises(ApiException):
        handler.check_step_health(ctx)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dagster_executors.py -v 2>&1 | tail -n 30`
Expected: FAIL at import, `teamster.core.executors` not found.

- [ ] **Step 3: Implement `ZombieAwareK8sStepHandler` in
      `src/teamster/core/executors.py`**

`check_step_health` returns `super().check_step_health(...)` when that result is
unhealthy. Otherwise it re-reads the Job status through
`self._api_client.get_job_status(namespace=..., job_name=...)` (same calls
upstream uses) and returns `CheckStepHealthResult.unhealthy(...)` when
`status.succeeded` and `status.completion_time` is more than
`ZOMBIE_JOB_GRACE_SECONDS` before `datetime.now(UTC)`. Reason text:
`f"Kubernetes job {job_name} for step {step_key} completed without a step result {age}s ago. Its replacement pod likely exited on Dagster's duplicate-start guard."`
Comment on the constant: one line saying it sits far above the run pod's lag in
reading a step's success event, so a healthy step never trips it (Refs #6103).
Class docstring (Google style) says what the extra rule catches; put the
upstream link `dagster-io/dagster#33755` in the extended description.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dagster_executors.py -v 2>&1 | tail -n 30`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/teamster/core/executors.py tests/test_dagster_executors.py
git commit -m "fix(dagster): report a step unhealthy when its Job completed without a result"
```

### Task 2: Wrapper executor, wiring, and runbook updates

**Files:**

- Modify: `src/teamster/core/executors.py`
- Modify:
  `src/teamster/code_locations/{kippnewark,kippmiami,kippcamden,kipptaf,kipppaterson}/definitions.py`
  (the `from dagster_k8s import k8s_job_executor` import and the
  `executor=k8s_job_executor` line in each)
- Modify: `.claude/skills/dagster-k8s-ops/SKILL.md` (the "Step pod replacement
  zombie" bullet)
- Modify: `.claude/skills/dagster-day2/SKILL.md:115` and
  `.claude/skills/dagster-day2/scripts/day2_collect.py:70`
- Test: `tests/test_dagster_executors.py`

**Interfaces:**

- Consumes: `ZombieAwareK8sStepHandler` from Task 1.
- Produces: `zombie_aware_k8s_job_executor: ExecutorDefinition` in
  `teamster.core.executors`.

- [ ] **Step 1: Write the failing tests**

```python
def test_wrapper_matches_stock_definition():
    assert zombie_aware_k8s_job_executor.name == k8s_job_executor.name
    assert zombie_aware_k8s_job_executor.config_schema == k8s_job_executor.config_schema
    # requirements: compare get_requirements({}) of both

def test_wrapper_installs_subclass_handler(monkeypatch):
    # Build via executor_creation_fn with a stub InitExecutorContext whose
    # executor_config is the schema's defaults (retries enabled) and whose
    # instance.run_launcher is not a K8sRunLauncher; patch
    # kubernetes.config.load_incluster_config to a no-op.
    executor = zombie_aware_k8s_job_executor.executor_creation_fn(init_context)
    assert isinstance(executor._step_handler, ZombieAwareK8sStepHandler)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dagster_executors.py -v 2>&1 | tail -n 30`
Expected: the 2 new tests fail on import of `zombie_aware_k8s_job_executor`.

- [ ] **Step 3: Implement `zombie_aware_k8s_job_executor`**

An
`@executor(name="k8s", config_schema=k8s_job_executor.config_schema, requirements=multiple_process_executor_requirements())`
function that calls `k8s_job_executor.executor_creation_fn(init_context)`,
checks the result with `check.inst(executor, StepDelegatingExecutor)` and
`check.inst(executor._step_handler, K8sStepHandler)`, then sets
`executor._step_handler.__class__ = ZombieAwareK8sStepHandler` and returns it.
The subclass adds no instance state, so the class swap keeps every field
upstream set. Docstring says it is `k8s_job_executor` with the zombie-aware
handler.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dagster_executors.py -v 2>&1 | tail -n 30`
Expected: 9 passed.

- [ ] **Step 5: Wire the 5 code locations**

In each `definitions.py`, replace the `dagster_k8s` import with
`from teamster.core.executors import zombie_aware_k8s_job_executor` and the
`executor=` value with `zombie_aware_k8s_job_executor`. Then:
`rg -n "k8s_job_executor" src/teamster/code_locations` must show only
`zombie_aware_k8s_job_executor`.

- [ ] **Step 6: Verify the code locations load**

Run `prepare-and-package` for `kippnewark`, then
`uv run dagster definitions validate -m teamster.code_locations.kippnewark.definitions 2>&1 | tail -n 5`.
Expected: validation succeeds. For the other 4, `uv run python -m py_compile`
each edited `definitions.py` (kipptaf and kippmiami do not import in the
codespace; see `src/teamster/CLAUDE.md`).

- [ ] **Step 7: Update the runbooks**

- `dagster-k8s-ops` zombie bullet: the run now fails the step about 60–80 s
  after the Job completes, with a health-check failure naming
  `completed without a step result`, and the auto-retry runs; the hang until
  `max_runtime` is gone. Keep the upstream link.
- `dagster-day2` "Step preempt-hang" row: match on `failed health check` +
  `completed without a step result` (keep the old `Exceeded maximum runtime`
  signature as a fallback for runs before this change). In `day2_collect.py`,
  add `"completed without a step result"` to that category's match list.

- [ ] **Step 8: Commit**

```bash
git add -u
git commit -m "fix(dagster): use the zombie-aware k8s executor in every code location"
```
