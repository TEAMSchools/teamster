# Midnight preemption Phase 1 (fewer pods per run) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run single-asset ADP, Forms and DeansList runs in the run pod, run
multi-asset DeansList runs in parallel inside one pod, and pull only edited
Forms.

**Architecture:** Each affected schedule targets an explicit `define_asset_job`
carrying its own `executor_def`, which overrides the code location's default
`zombie_aware_k8s_job_executor` for that job only. The Forms schedule filters
its partition keys by Drive `modifiedTime`.

**Tech Stack:** Dagster (`define_asset_job`, `in_process_executor`,
`multiprocess_executor`), `GoogleDriveResource`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-midnight-preemption-design.md`
(Phase 1). Issue #6226; parent #6225.

## Global Constraints

- Every other job keeps `zombie_aware_k8s_job_executor`. Do not touch any
  `definitions.py` executor.
- Step parallelism is preserved: a multi-asset run uses `multiprocess_executor`
  with `max_concurrent` equal to its asset count.
- Each ADP partition stays its own run. No cron changes.
- Forms window: request a form when its `modifiedTime` is within the last 25
  hours of the tick.
- Look up Forms partition keys, never the folder listing.
- Always `uv run`; worktree is
  `/workspaces/teamster/.claude/worktrees/cbini/fix/claude-midnight-preemption`
  (use `git -C <worktree>` and absolute paths).
- Never bare `uv run pytest`: run only the named test files.

## Review Focus

1. A form whose Drive lookup fails (`get_modified_times()` omits it: 403 on a
   personal My Drive file, deleted file) must still get a run, not silently drop
   out. Test in Task 3.
2. A tick with no `scheduled_execution_time` (manual test tick) must fall back
   to now, not crash. Test in Task 3.
3. Multiprocess static runs (5 steps) may exceed the 2.5 GiB run-pod memory
   limit. Measured in Task 4.
4. Job names change from `__anonymous_asset_job_<schedule>` to the new names.
   Alert policies, Insights views, or scripts keyed on the old names stop
   matching. Checked in Task 4.
5. A job name that equals its schedule name (the midday comm log job) may
   collide. Task 1 gives it an explicit name; Task 4's definitions validation
   proves no collision.

---

### Task 1: DeansList schedules target a job with an executor by asset count

**Files:**

- Modify: `src/teamster/libraries/deanslist/schedules.py`
- Modify:
  `src/teamster/code_locations/{kippnewark,kippcamden,kipppaterson}/deanslist/schedules.py`
  (midday schedule only; Paterson has none, skip it if absent)
- Test: `tests/schedules/test_schedules_deanslist.py`

**Interfaces:**

- Produces:
  `build_deanslist_job_schedule(schedule_name, cron_schedule, execution_timezone, asset_selection, current_fiscal_year=None, lookback_months=0, job_name: str | None = None) -> ScheduleDefinition`.
  `job_name` defaults to `schedule_name.removesuffix("_schedule")`.

- [ ] **Step 1: Write the failing tests**

In `tests/schedules/test_schedules_deanslist.py`, build two throwaway assets
sharing one `StaticPartitionsDefinition(["1"])`, then:

```python
def test_deanslist_single_asset_runs_in_process():
    s = build_deanslist_job_schedule(
        schedule_name="x__deanslist__month_partitioned_asset_job_schedule",
        cron_schedule="0 0 * * *", execution_timezone="America/New_York",
        asset_selection=[a1],
    )
    job = Definitions(assets=[a1], schedules=[s]).resolve_job_def(
        "x__deanslist__month_partitioned_asset_job"
    )
    assert job.executor_def.name == "in_process"


def test_deanslist_multi_asset_runs_multiprocess():
    # same with asset_selection=[a1, a2]
    assert job.executor_def.name == "multiprocess"


def test_deanslist_explicit_job_name():
    # schedule_name="x__deanslist__midday_commlog_job", job_name="x__deanslist__midday_commlog_asset_job"
    # resolve_job_def("x__deanslist__midday_commlog_asset_job") succeeds
```

- [ ] **Step 2: Run to verify they fail**

Run:
`uv run pytest tests/schedules/test_schedules_deanslist.py -v -k "in_process or multiprocess or explicit_job_name"`
Expected: FAIL (`resolve_job_def` finds no job by that name).

- [ ] **Step 3: Implement**

In the factory, build
`define_asset_job(name=job_name, selection=asset_selection, executor_def=...)`
and pass it as the schedule `target`. Executor: `in_process_executor` when
`len(asset_selection) == 1`, else
`multiprocess_executor.configured({"max_concurrent": len(asset_selection)})`.
`RunRequest`s are unchanged (they still set `asset_selection` and
`partition_key`). In each district's midday schedule, pass
`job_name=f"{CODE_LOCATION}__deanslist__midday_commlog_asset_job"`.

- [ ] **Step 4: Run all DeansList schedule tests**

Run: `uv run pytest tests/schedules/test_schedules_deanslist.py -v` Expected:
the 3 new tests and `test_deanslist_schedule_lookback_months` PASS. The live
`_test_schedule` helper is not collected.

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/libraries/deanslist/schedules.py src/teamster/code_locations/kippnewark/deanslist/schedules.py src/teamster/code_locations/kippcamden/deanslist/schedules.py tests/schedules/test_schedules_deanslist.py
git -C <worktree> commit -m "fix(deanslist): run schedules without step pods, keep steps parallel"
```

### Task 2: ADP workers schedule runs in process

**Files:**

- Modify:
  `src/teamster/code_locations/kipptaf/adp/workforce_now/api/schedules.py`
- Test: `tests/schedules/test_schedules_adp.py`

**Interfaces:**

- Produces: job `kipptaf__adp__workforce_now__workers_asset_job`
  (`f"{adp_workforce_now_workers.key.to_python_identifier()}_asset_job"`).

- [ ] **Step 1: Write the failing test**

```python
def test_adp_workers_schedule_runs_in_process():
    from teamster.code_locations.kipptaf.adp.workforce_now.api.schedules import (
        adp_workforce_now_api_workers_asset_schedule as s,
    )
    assert s.job_name == "kipptaf__adp__workforce_now__workers_asset_job"
    assert s.job.executor_def.name == "in_process"
```

If `s.job` does not resolve an unresolved asset job, resolve through
`Definitions(assets=[adp_workforce_now_workers], schedules=[s]).resolve_job_def(...)`.

- [ ] **Step 2: Run to verify it fails**

Run:
`uv run pytest tests/schedules/test_schedules_adp.py::test_adp_workers_schedule_runs_in_process -v`
Expected: FAIL (anonymous job name).

- [ ] **Step 3: Implement**

`target=define_asset_job(name=..., selection=[adp_workforce_now_workers], executor_def=in_process_executor)`.
The schedule body, cron, and the sync schedule are unchanged.

- [ ] **Step 4: Run to verify it passes**

Same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/code_locations/kipptaf/adp/workforce_now/api/schedules.py tests/schedules/test_schedules_adp.py
git -C <worktree> commit -m "fix(adp): run the nightly workers pull without step pods"
```

### Task 3: Forms schedule pulls only edited forms, in process

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/google/forms/schedules.py`
- Test: `tests/schedules/test_schedules_google_forms.py`

**Interfaces:**

- Consumes:
  `GoogleDriveResource.get_modified_times(file_ids: list[str], *, logger=None) -> dict[str, float]`
  (POSIX seconds; failed lookups are omitted from the dict).
- Produces: job `kipptaf__google__forms__form_asset_job`; the schedule function
  takes `google_drive: GoogleDriveResource`.

- [ ] **Step 1: Write the failing tests**

Use `DagsterInstance.ephemeral()`, add dynamic partitions `["a", "b", "c"]` to
`GOOGLE_FORMS_PARTITIONS_DEF.name`, and pass a stub resource
(`SimpleNamespace(get_modified_times=lambda file_ids, logger=None: {...})`)
through
`build_schedule_context(instance=..., resources={"google_drive": stub}, scheduled_execution_time=tick)`.

```python
def test_forms_schedule_requests_only_recent_edits():
    # tick = 2026-11-03 00:00 ET; "a" modified 1h before, "b" 26h before, "c" lookup failed (omitted)
    keys = sorted(r.partition_key for r in run_requests)
    assert keys == ["a", "c"]


def test_forms_schedule_without_tick_time_uses_now():
    # scheduled_execution_time omitted; "a" modified 1 minute ago (time.time() - 60)
    assert [r.partition_key for r in run_requests] == ["a"]


def test_forms_schedule_runs_in_process():
    assert job.executor_def.name == "in_process"  # job name kipptaf__google__forms__form_asset_job
```

Keep the existing live `test_schedule` but pass a real `google_drive` resource
or mark it so it is not run here; do not run it in this task.

- [ ] **Step 2: Run to verify they fail**

Run:
`uv run pytest tests/schedules/test_schedules_google_forms.py -v -k "recent_edits or without_tick or in_process"`
Expected: FAIL.

- [ ] **Step 3: Implement**

Target
`define_asset_job(name=f"{form.key.to_python_identifier()}_asset_job", selection=[form], executor_def=in_process_executor)`.
Add `google_drive: GoogleDriveResource` to the schedule function. Cutoff is
`(context.scheduled_execution_time or now) - 25 hours`. Yield a `RunRequest`
(same `run_key` and `partition_key` as today) for each key whose
`modifiedTime >= cutoff` or whose key is missing from the lookup result. Pass
`logger=context.log`. Add the comment
`# shortcut: a failed form run is not retried the next night unless the form is edited again; materialize it by hand.`

- [ ] **Step 4: Run to verify they pass**

Same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/code_locations/kipptaf/google/forms/schedules.py tests/schedules/test_schedules_google_forms.py
git -C <worktree> commit -m "fix(google-forms): pull only forms edited since the last nightly run"
```

### Task 4: Validate, check job-name consumers, open the PR, measure memory

**Files:** none unless a check fails.

- [ ] **Step 1: Build manifests and validate definitions**

Run, from the worktree, for `kipptaf kippnewark kippcamden kipppaterson`:
`uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/<loc>/__init__.py`,
then
`uv run pytest tests/test_dagster_definitions.py -v -k "kipptaf or kippnewark or kippcamden or kipppaterson" 2>&1 | tail -n 30`.
Expected: those 4 PASS (`kippmiami` and `test_definitions_all` fail in the
codespace regardless; see `src/teamster/CLAUDE.md`).

- [ ] **Step 2: Check consumers of the old job names**

Search the repo (`rg -n "__anonymous_asset_job_" --glob '!docs/superpowers/**'`)
and Dagster+ alert policies
(`mcp__dagster-plus__get_alert_policies_as_document`, `deployment_name="prod"`)
for the old names of the 4 changed schedules. Expected: no hits. Any hit gets
updated in this PR.

- [ ] **Step 3: Lint and push**

`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed files> </dev/null`
from the worktree; fix findings. Push, then open a ready (not draft) PR from
`.github/pull_request_template.md` with `Closes #6226` and `Refs #6225`.

- [ ] **Step 4: Measure multiprocess memory on the branch deployment**

On the PR's branch deployment, launch one `kippnewark` DeansList static
partition and one year partition. Read the run pod's peak memory
(`kubernetes.io/container/memory/used_bytes`, max over the run). Expected: below
2.5 GiB with margin. If not, add a `dagster-k8s/config` tag with raised
`resources` to the multi-asset jobs in the factory, and re-measure.

- [ ] **Step 5: Confirm one in-process run per job**

On the branch deployment, launch one partition each of the ADP workers, Forms
`form`, and DeansList month jobs. Expected: each succeeds and starts no
`dagster-step-*` pod.
