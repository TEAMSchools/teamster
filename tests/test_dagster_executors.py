from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import kubernetes.config
import pytest
from dagster_k8s import k8s_job_executor
from dagster_k8s.executor import K8sStepHandler
from kubernetes.client import V1JobStatus
from kubernetes.client.exceptions import ApiException

from teamster.core.executors import (
    ZombieAwareK8sStepHandler,
    zombie_aware_k8s_job_executor,
)

JOB_NAME = "dagster-step-abc"


def _handler(
    status: V1JobStatus | None, error: Exception | None = None
) -> ZombieAwareK8sStepHandler:
    # skip __init__, which loads kube config
    handler = object.__new__(ZombieAwareK8sStepHandler)
    api_client = Mock()
    api_client.get_job_status.return_value = status
    api_client.get_job_status.side_effect = error
    handler._api_client = api_client
    object.__setattr__(handler, "_get_step_key", lambda _: "my_step")
    object.__setattr__(handler, "_get_k8s_step_job_name", lambda _: JOB_NAME)
    object.__setattr__(
        handler,
        "_get_container_context",
        lambda _: SimpleNamespace(namespace="dagster-cloud"),
    )
    return handler


def _completed(seconds_ago: int) -> V1JobStatus:
    return V1JobStatus(
        succeeded=1, completion_time=datetime.now(UTC) - timedelta(seconds=seconds_ago)
    )


def test_succeeded_past_grace_is_unhealthy():
    result = _handler(_completed(121)).check_step_health(Mock())

    assert not result.is_healthy
    assert "completed without a step result" in str(result.unhealthy_reason)
    assert JOB_NAME in str(result.unhealthy_reason)


def test_succeeded_inside_grace_is_healthy():
    assert _handler(_completed(90)).check_step_health(Mock()).is_healthy


def test_succeeded_without_completion_time_is_healthy():
    status = V1JobStatus(succeeded=1, completion_time=None)

    assert _handler(status).check_step_health(Mock()).is_healthy


def test_running_job_is_healthy():
    assert _handler(V1JobStatus(active=1)).check_step_health(Mock()).is_healthy


@pytest.mark.parametrize("status", [None, V1JobStatus(failed=1)])
def test_missing_or_failed_job_matches_upstream(status):
    # the handler copies upstream's checks; this fails if a dagster-k8s upgrade
    # changes them
    handler = _handler(status)

    result = handler.check_step_health(Mock())
    upstream = K8sStepHandler.check_step_health(handler, Mock())

    assert not result.is_healthy
    assert result.unhealthy_reason == upstream.unhealthy_reason


def test_reads_job_status_once_per_check():
    handler = _handler(_completed(121))

    handler.check_step_health(Mock())

    get_job_status = handler._api_client.get_job_status
    assert isinstance(get_job_status, Mock)
    assert get_job_status.call_count == 1


def test_status_api_error_propagates():
    handler = _handler(None, error=ApiException(status=500))

    with pytest.raises(ApiException):
        handler.check_step_health(Mock())


def test_wrapper_matches_stock_definition():
    assert zombie_aware_k8s_job_executor.name == k8s_job_executor.name
    assert zombie_aware_k8s_job_executor.config_schema == k8s_job_executor.config_schema
    assert zombie_aware_k8s_job_executor.get_requirements(
        {}
    ) == k8s_job_executor.get_requirements({})


def test_wrapper_installs_subclass_handler(monkeypatch):
    monkeypatch.setattr(kubernetes.config, "load_incluster_config", lambda: None)
    # the creation fn reads only these two attributes
    init_context = SimpleNamespace(
        instance=SimpleNamespace(run_launcher=None),
        executor_config={"retries": {"enabled": {}}},
    )

    executor = zombie_aware_k8s_job_executor.executor_creation_fn(init_context)  # type: ignore[arg-type]

    handler = executor._step_handler  # type: ignore[attr-defined]
    assert isinstance(handler, ZombieAwareK8sStepHandler)
    # _handler() stubs these, so only the real instance catches an upstream rename
    for name in (
        "_get_step_key",
        "_get_k8s_step_job_name",
        "_get_container_context",
        "_api_client",
    ):
        assert hasattr(handler, name), name
