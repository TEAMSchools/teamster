from datetime import UTC, datetime

from dagster import (
    Executor,
    InitExecutorContext,
    executor,
    multiple_process_executor_requirements,
)
from dagster._core.executor.step_delegating import StepDelegatingExecutor
from dagster._core.executor.step_delegating.step_handler.base import (
    CheckStepHealthResult,
    StepHandlerContext,
)
from dagster_k8s import k8s_job_executor
from dagster_k8s.executor import K8sStepHandler
from dagster_shared import check

# Far above the run pod's lag in reading a step's success event. A healthy step
# that tripped it would fail the whole run when its late success arrives
# (Dagster's in-flight invariant), so err long (Refs #6103).
ZOMBIE_JOB_GRACE_SECONDS = 120


class ZombieAwareK8sStepHandler(K8sStepHandler):
    """K8sStepHandler that also fails a step whose Job completed silently.

    When a step pod is disrupted after the step starts, the Job's replacement
    pod exits 0 on Dagster's duplicate-start guard. The Job then reads Complete,
    the stock health check reports healthy, and the run hangs until
    `max_runtime`. This handler reports a step unhealthy once its Job has
    completed for longer than `ZOMBIE_JOB_GRACE_SECONDS` while the run still
    treats the step as running.

    Upstream: https://github.com/dagster-io/dagster/issues/33755
    """

    def check_step_health(
        self, step_handler_context: StepHandlerContext
    ) -> CheckStepHealthResult:
        result = super().check_step_health(step_handler_context)
        if not result.is_healthy:
            return result

        step_key = self._get_step_key(step_handler_context)
        job_name = self._get_k8s_step_job_name(step_handler_context)
        container_context = self._get_container_context(step_handler_context)

        status = self._api_client.get_job_status(
            namespace=check.not_none(container_context.namespace), job_name=job_name
        )
        if status is None or not status.succeeded or status.completion_time is None:
            return result

        age = (datetime.now(UTC) - status.completion_time).total_seconds()
        if age <= ZOMBIE_JOB_GRACE_SECONDS:
            return result

        return CheckStepHealthResult.unhealthy(
            reason=(
                f"Kubernetes job {job_name} for step {step_key} completed without "
                f"a step result {age:.0f}s ago. Its replacement pod likely exited "
                "on Dagster's duplicate-start guard."
            )
        )


@executor(
    name=k8s_job_executor.name,
    # trunk-ignore(pyright/reportArgumentType): the same schema object upstream passes in
    config_schema=k8s_job_executor.config_schema,
    requirements=multiple_process_executor_requirements(),
)
def zombie_aware_k8s_job_executor(init_context: InitExecutorContext) -> Executor:
    """`k8s_job_executor` with `ZombieAwareK8sStepHandler` as its step handler."""
    step_executor = check.inst(
        check.not_none(k8s_job_executor.executor_creation_fn)(init_context),
        StepDelegatingExecutor,
    )
    # the subclass adds no instance state, so swapping the class keeps every
    # field upstream set
    check.inst(
        step_executor._step_handler, K8sStepHandler
    ).__class__ = ZombieAwareK8sStepHandler
    return step_executor
