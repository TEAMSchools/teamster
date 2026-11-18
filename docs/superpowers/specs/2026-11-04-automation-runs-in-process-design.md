# Automation runs in process

Refs #6257 (parent #6225).

## Intent

Automation-sensor runs start about 1,050 step pods a day across the 5 code
locations, and in 99% of them the step pod runs one op. Each pod adds to the
hourly bursts that make GKE add nodes, and new nodes are where our pods get
preempted (#6225). Running those one-step runs inside the run pod removes the
step pod without losing any parallelism.

## Goals, non-goals, anti-goals

- Goal: one-step runs launched by an automation-condition sensor start no step
  pod.
- Non-goal: changing any other run. Schedules, other sensors, backfills, and
  manual "Materialize" clicks keep their executor and pod sizing.
- Anti-goal: dbt automation runs that run out of memory or get slower.

## Constraints

- Dagster cannot set an executor per automation sensor. `__ASSET_JOB` takes the
  `Definitions(executor=...)` default, and the daemon only routes asset runs to
  jobs named `__ASSET_JOB*` (`submit_asset_runs.py`,
  `_get_implicit_job_name_for_assets`, Dagster 1.13.28).
- `__ASSET_JOB` also carries manual launches and backfills. Some assets size
  their own step pod through `op_tags` (kippmiami Focus dlt requests 4 GiB);
  those must keep their step pod.
- In process, `op_tags` `dagster-k8s/config` no longer apply. dbt `op_tags` only
  raise the CPU limit; the run pod's limit is 1.75 cores.

## Approaches

1. **Per-run dispatch in our executor, gated on the automation tag and one step
   (picked).** The daemon tags every run it launches
   `dagster/from_automation_condition=true`. Only those runs change.
2. Gate on `job_name.startswith("__ASSET_JOB")`. Rejected: also moves manual
   launches and backfills of heavy assets into a 2 GiB run pod.
3. Change the location default to in process or multiprocess and set the k8s
   executor on every job that needs step pods. Rejected: touches every job, and
   any job that forgets an executor silently changes.

Copying the dbt CPU limits to the run pod through each sensor's `run_tags` was
measured and dropped. Over 7 days, 2 of about 5,200 dbt step pods had a 60 s
peak above 1.75 cores (max 1.83). Those would be briefly throttled, not fail.

## Design

- `src/teamster/core/executors.py`: `zombie_aware_k8s_job_executor` returns an
  executor that wraps the existing `StepDelegatingExecutor`. In `execute`, if
  the run's tags carry `dagster/from_automation_condition=true` and the plan has
  exactly 1 step to execute, it hands the plan to an `InProcessExecutor` with
  the same retry mode. Otherwise it hands the plan to the step executor
  unchanged.
- The executor name and config schema stay the same, so no `Definitions`, job,
  or sensor changes.
- Tests: one unit test per branch (tagged one-step in process, untagged one-step
  and tagged two-step to the step executor).

## Checks

- Branch deployment: launch a one-step kipptaf dbt run with the automation tag
  added. Compare peak memory and run time against today's step pods.
- After merge: 2 weeks with no OOM or runtime regression in dbt automation
  (#6257 "fixed means").

## Left to the builder

- How to read the run's tags inside `execute` (`plan_context.dagster_run.tags`
  is the expected path).
- Whether the wrapper is a small class next to `ZombieAwareK8sStepHandler` or a
  function; keep it the smallest that tests cleanly.
