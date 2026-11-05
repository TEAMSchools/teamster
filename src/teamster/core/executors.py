from collections.abc import Iterator, Mapping
from datetime import UTC, datetime

from dagster import (
    DagsterEvent,
    Executor,
    InitExecutorContext,
    executor,
    multiple_process_executor_requirements,
)
from dagster._core.execution.context.system import PlanOrchestrationContext
from dagster._core.execution.plan.plan import ExecutionPlan
from dagster._core.execution.retries import RetryMode
from dagster._core.execution.step_dependency_config import StepDependencyConfig
from dagster._core.executor.in_process import InProcessExecutor
from dagster._core.executor.step_delegating import StepDelegatingExecutor
from dagster._core.executor.step_delegating.step_handler.base import (
    CheckStepHealthResult,
    StepHandlerContext,
)
from dagster._core.storage.tags import AUTOMATION_CONDITION_TAG
from dagster_k8s import k8s_job_executor
from dagster_k8s.executor import K8sStepHandler
from dagster_k8s.job import get_user_defined_k8s_config
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
        step_key = self._get_step_key(step_handler_context)
        job_name = self._get_k8s_step_job_name(step_handler_context)
        container_context = self._get_container_context(step_handler_context)

        status = self._api_client.get_job_status(
            namespace=check.not_none(container_context.namespace), job_name=job_name
        )

        # the missing and failed checks copy upstream's, so its Job status read
        # is not repeated; re-sync them on a dagster-k8s upgrade
        if not status:
            return CheckStepHealthResult.unhealthy(
                reason=f"Kubernetes job {job_name} for step {step_key} could not be found."
            )
        if status.failed:
            return CheckStepHealthResult.unhealthy(
                reason=f"Discovered failed Kubernetes job {job_name} for step {step_key}.",
            )

        if not status.succeeded or status.completion_time is None:
            return CheckStepHealthResult.healthy()

        age = (datetime.now(UTC) - status.completion_time).total_seconds()
        if age <= ZOMBIE_JOB_GRACE_SECONDS:
            return CheckStepHealthResult.healthy()

        return CheckStepHealthResult.unhealthy(
            reason=(
                f"Kubernetes job {job_name} for step {step_key} completed without "
                f"a step result {age:.0f}s ago. Its replacement pod likely exited "
                "on Dagster's duplicate-start guard."
            )
        )


class AutomationInProcessExecutor(Executor):
    """Runs one-step automation-sensor runs in process, everything else in step pods.

    Almost every automation run materializes a single op, so a step pod adds a pod
    without adding parallelism. Each extra pod feeds the node scale-ups where GKE
    preempts our pods. Manual launches and user-launched backfills keep step pods.
    Backfills the automation daemon creates carry its tag, so their one-step runs
    also run in process.

    In process, op-level `dagster-k8s/config` tags do not apply; the step runs with
    the run pod's resources. An op that sizes its own memory keeps its step pod, so
    adding an automation condition to it cannot shrink it into the run pod. Ops
    that only raise CPU run in process and get the run pod's CPU limit.
    """

    def __init__(self, step_executor: Executor):
        self._step_executor = step_executor
        self._in_process = InProcessExecutor(
            retries=step_executor.retries,
            step_dependency_config=step_executor.step_dependency_config,
        )

    @property
    def retries(self) -> RetryMode:
        return self._step_executor.retries

    @property
    def step_dependency_config(self) -> StepDependencyConfig:
        return self._step_executor.step_dependency_config

    def execute(
        self, plan_context: PlanOrchestrationContext, execution_plan: ExecutionPlan
    ) -> Iterator[DagsterEvent]:
        from_automation = (
            plan_context.dagster_run.tags.get(AUTOMATION_CONDITION_TAG) == "true"
        )
        step_keys = execution_plan.step_keys_to_execute

        in_process = (
            from_automation
            and len(step_keys) == 1
            and not _sizes_own_memory(execution_plan.get_step_by_key(step_keys[0]).tags)
        )

        target = self._in_process if in_process else self._step_executor
        yield from target.execute(plan_context, execution_plan)


def _sizes_own_memory(op_tags: Mapping[str, str] | None) -> bool:
    """Whether an op's `dagster-k8s/config` tags request or limit memory."""
    resources = get_user_defined_k8s_config(op_tags or {}).container_config.get(
        "resources", {}
    )
    return any("memory" in resources.get(kind, {}) for kind in ("requests", "limits"))


@executor(
    name=k8s_job_executor.name,
    # trunk-ignore(pyright/reportArgumentType): the same schema object upstream passes in
    config_schema=k8s_job_executor.config_schema,
    requirements=multiple_process_executor_requirements(),
)
def zombie_aware_k8s_job_executor(init_context: InitExecutorContext) -> Executor:
    """`k8s_job_executor` with `ZombieAwareK8sStepHandler` as its step handler.

    Wrapped in `AutomationInProcessExecutor`, so one-step automation-sensor runs
    run in process instead of in a step pod.
    """
    step_executor = check.inst(
        check.not_none(k8s_job_executor.executor_creation_fn)(init_context),
        StepDelegatingExecutor,
    )
    # the subclass adds no instance state, so swapping the class keeps every
    # field upstream set; do not give it an __init__ or attributes of its own
    check.inst(
        step_executor._step_handler, K8sStepHandler
    ).__class__ = ZombieAwareK8sStepHandler
    return AutomationInProcessExecutor(step_executor)
