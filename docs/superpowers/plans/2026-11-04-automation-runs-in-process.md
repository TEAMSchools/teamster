# Automation Runs In Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** One-step runs launched by an automation-condition sensor run in
process inside the run pod; every other run keeps k8s step pods.

**Architecture:** `zombie_aware_k8s_job_executor` returns a small wrapper
executor around the existing `StepDelegatingExecutor`. Per run, `execute` picks
an `InProcessExecutor` when the run carries the automation tag and the plan has
exactly one step, and the step executor otherwise.

**Tech Stack:** Dagster 1.13.28, dagster-k8s, pytest.

**Spec:**
`docs/superpowers/specs/2026-11-04-automation-runs-in-process-design.md`

## Global Constraints

- Gate: run tag `dagster/from_automation_condition` equals `"true"` AND
  `len(execution_plan.step_keys_to_execute) == 1`. Use Dagster's
  `AUTOMATION_CONDITION_TAG` constant from `dagster._core.storage.tags`, not a
  string literal.
- Executor name, config schema, and requirements stay identical to
  `k8s_job_executor` (existing `test_wrapper_matches_stock_definition` must
  still pass unchanged).
- No changes to any `definitions.py`, job, or sensor.
- Run tests with `uv run pytest tests/test_dagster_executors.py`, from the
  worktree root, never bare `pytest`.
- Runtime type narrowing with `dagster_shared.check`, never `assert isinstance`.

## Review Focus

- Retry mode: the in-process path must use the step executor's `retries`, or a
  RetryPolicy (the Google Sheets dbt op's delayed retry) silently stops
  retrying. Pinned in Task 1 (`test_in_process_shares_retry_mode`).
- A re-execution of a failed automation run copies its tags, so it also runs in
  process. Expected; no test, mention in the PR.
- A tag value other than `"true"` (for example `"false"`) must go to step pods.
  Pinned in Task 1 (`test_tag_not_true_uses_step_pods`).
- `step_dependency_config` must forward to the step executor so dependency
  settings from executor config still apply. Pinned in Task 1.
- The wrapper must not break the zombie handler install: the existing subclass
  test is updated to reach the handler through the wrapper (Task 1), not
  deleted.

---

### Task 1: Dispatching executor

**Files:**

- Modify: `src/teamster/core/executors.py` (add class after
  `ZombieAwareK8sStepHandler`; change the return of
  `zombie_aware_k8s_job_executor`)
- Test: `tests/test_dagster_executors.py`

**Interfaces:**

- Produces: `class AutomationInProcessExecutor(Executor)` in
  `teamster.core.executors`, with `__init__(self, step_executor: Executor)`,
  attributes `_step_executor: Executor` and `_in_process: InProcessExecutor`,
  properties `retries -> RetryMode` and
  `step_dependency_config -> StepDependencyConfig` (both forwarded from
  `_step_executor`), and
  `execute(plan_context, execution_plan) -> Iterator[DagsterEvent]`.
- `zombie_aware_k8s_job_executor(init_context)` returns
  `AutomationInProcessExecutor(step_executor)` where `step_executor` is the
  `StepDelegatingExecutor` it builds today.

- [ ] **Step 1: Write the failing tests** in `tests/test_dagster_executors.py`.
      Build contexts with `SimpleNamespace`; replace `_in_process` and
      `_step_executor` with `Mock(execute=Mock(return_value=iter(["event"])))`
      after construction.

```python
def _dispatch(tags: dict[str, str], step_keys: list[str]):
    step = Mock(retries=RetryMode.ENABLED)
    executor = AutomationInProcessExecutor(step)
    executor._in_process = Mock(execute=Mock(return_value=iter(["in"])))
    step.execute = Mock(return_value=iter(["step"]))
    plan_context = SimpleNamespace(dagster_run=SimpleNamespace(tags=tags))
    plan = SimpleNamespace(step_keys_to_execute=step_keys)
    return list(executor.execute(plan_context, plan))  # type: ignore[arg-type]


AUTO = {AUTOMATION_CONDITION_TAG: "true"}

def test_automation_one_step_runs_in_process():
    assert _dispatch(AUTO, ["a"]) == ["in"]

def test_automation_two_steps_use_step_pods():
    assert _dispatch(AUTO, ["a", "b"]) == ["step"]

def test_untagged_one_step_uses_step_pods():
    assert _dispatch({}, ["a"]) == ["step"]

def test_tag_not_true_uses_step_pods():
    assert _dispatch({AUTOMATION_CONDITION_TAG: "false"}, ["a"]) == ["step"]

def test_in_process_shares_retry_mode():
    executor = AutomationInProcessExecutor(Mock(retries=RetryMode.DISABLED))
    assert executor.retries == RetryMode.DISABLED
    assert executor._in_process.retries == RetryMode.DISABLED

def test_forwards_step_dependency_config():
    config = Mock()
    executor = AutomationInProcessExecutor(
        Mock(retries=RetryMode.ENABLED, step_dependency_config=config)
    )
    assert executor.step_dependency_config is config
```

      Update `test_wrapper_installs_subclass_handler`: assert the returned
      executor is an `AutomationInProcessExecutor`, then read the handler from
      `executor._step_executor._step_handler`; the rest of the test stays.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dagster_executors.py -q 2>&1 | tail -n 15`
Expected: collection error, `cannot import name 'AutomationInProcessExecutor'`.

- [ ] **Step 3: Implement `AutomationInProcessExecutor` and wire it into
      `zombie_aware_k8s_job_executor`** in `src/teamster/core/executors.py`.
      `__init__` builds `InProcessExecutor(retries=step_executor.retries)`.
      `execute` reads
      `plan_context.dagster_run.tags.get(AUTOMATION_CONDITION_TAG)     == "true"`
      and the step-key count, then `yield from` the chosen executor.
      Google-style class docstring: what it does and why (a step pod per one-op
      automation run adds to the node-scale-up bursts where GKE preempts pods),
      plus a one-line note that op-level `dagster-k8s/config` does not apply in
      process. Update the `zombie_aware_k8s_job_executor` docstring to say it
      also runs one-step automation runs in process.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dagster_executors.py -q 2>&1 | tail -n 5`
Expected: every test passes, including the 6 new ones and the updated subclass
test.

- [ ] **Step 5: Real-path smoke test.** Run the throwaway check at
      `/tmp/claude-1000/-workspaces-teamster/08dc0f66-d08b-40ce-ae21-376773fcf867/scratchpad/dispatch_smoke/`
      adapted to import `AutomationInProcessExecutor` from
      `teamster.core.executors` and wrap `multiprocess_executor` in place of the
      k8s one; launch the one-step job with `tags=AUTO` and without. Expected:
      tagged run logs "Executing steps in process"; untagged run does not. Both
      succeed. Do not commit the smoke test.

- [ ] **Step 6: Commit**

```bash
git add -u && git commit -F <scratchpad>/commit-msg-automation-in-process.txt
```

Message: `fix: run one-step automation runs in process` with a body naming the
gate and `Refs #6257`.

### Task 2: Branch-deployment check and PR

**Files:** none changed.

- [ ] **Step 1: Open the PR (ready for review, not draft)** from
      `.github/pull_request_template.md`, `Refs #6257`, so the branch deployment
      builds.
- [ ] **Step 2: Wait for the kipptaf branch deployment** and read its deployment
      name from the deploy job log.
- [ ] **Step 3: Launch one kipptaf core dbt run in that deployment** for a
      single small model, with tag `dagster/from_automation_condition=true`.
      State the target in plain text before launching. Expected: the run
      succeeds, its logs show "Executing steps in process", and no
      `dagster-step-*` pod is created for it.
- [ ] **Step 4: Record peak memory and run time** (60 s ALIGN_MAX non-evictable
      memory on the run pod) against a recent prod step pod for the same op, and
      add both to the PR body's Reviewer Notes.
