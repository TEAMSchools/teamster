# Fail fast on zombie step Jobs — design

Refs #6103. Upstream: dagster-io/dagster#33755.

## Intent

A step pod killed after `STEP_START` gets a replacement pod (our
`podFailurePolicy` ignores `DisruptionTarget`). The replacement exits 0 on
Dagster's duplicate-start guard, the Job reads Complete, and
`K8sStepHandler.check_step_health` reports healthy. The run then hangs until
`max_runtime`. Make that case fail the step within about a minute so the run's
auto-retry takes over.

## Goals

- A step whose Job succeeded, but whose terminal step event the run pod never
  read, fails about 60–80 s after the Job completed.
- All 5 code locations get it.

## Non-goals

- Changing `podFailurePolicy`, `backoffLimit`, or pod placement. Most
  disruptions land before `STEP_START` and recover through the replacement pod;
  that path stays as is.
- Retrying the step in place. The existing run-level auto-retry handles it.

## Anti-goals

- Failing a step that actually succeeded.
- Forking `k8s_job_executor`'s setup code.

## How it works today

`StepDelegatingExecutor` calls `check_step_health` every 20 s, only for steps it
still treats as running: it has not yet read their `STEP_SUCCESS` or
`STEP_FAILURE`. An unhealthy result goes through
`log_failure_or_retry_event_after_error`, the same path a failed Job takes.

## Measurement

Across 17 prod steps on 2026-10-23, the run pod read `STEP_SUCCESS` at most 2.9
s after the step wrote it, and always 2.4–10.6 s before the Job reported
Complete. So "Job complete but success unread" never occurred for a healthy
step. A 60 s grace period is more than 20 times the worst observed lag.

## Approaches

1. **Copy `k8s_job_executor`'s init** (about 90 lines) into our own executor
   that builds a subclass handler. Explicit, but drifts silently on
   `dagster-k8s` upgrades.
2. **Wrap `k8s_job_executor`** (picked). Call the stock executor's creation
   function, then swap the handler on the returned `StepDelegatingExecutor` for
   our subclass. About 10 lines, keeps every upstream config field. Relies on
   the private `_step_handler` attribute, which a test pins.
3. **Upstream fix only.** Correct long-term, but leaves us hanging until a
   release lands.

Charlie picked 2: fork as little as possible.

## Decided

- New module `src/teamster/core/executors.py` holds:
  - A `K8sStepHandler` subclass whose `check_step_health` first calls `super()`.
    If that result is healthy and the Job status shows `succeeded` with a
    `completion_time` more than 60 s ago, it returns unhealthy with a reason
    naming the Job and the duplicate-start guard.
  - An executor definition with the same name and config schema as
    `k8s_job_executor`. It builds the stock executor and replaces its step
    handler with the subclass, keeping the handler's existing state.
- The 5 `definitions.py` files import the new executor instead of
  `k8s_job_executor`.
- Grace period: a 60 s module constant with a one-line comment on why.

## Left to the builder

- How the handler is swapped (re-instantiate from the stock handler's fields, or
  reassign its class), as long as no upstream init code is copied.
- Test shape. Tests must cover: succeeded Job past the grace period → unhealthy;
  succeeded Job inside the grace period → healthy; running Job → healthy; failed
  or missing Job → upstream's unhealthy result unchanged; the executor built
  from the wrapper carries the subclass handler.
