from datetime import UTC, datetime

from dagster._core.executor.step_delegating.step_handler.base import (
    CheckStepHealthResult,
    StepHandlerContext,
)
from dagster_k8s.executor import K8sStepHandler
from dagster_shared import check

# Far above the run pod's lag in reading a step's success event, so a healthy
# step never trips it (Refs #6103).
ZOMBIE_JOB_GRACE_SECONDS = 60


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
