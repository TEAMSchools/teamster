import signal
from contextlib import contextmanager

from dagster import DagsterRunStatus
from dagster._core.storage.pipeline_run import RunsFilter

from teamster.core.utils.variables import LOCAL_TIME_ZONE


@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutError(f"Timed out after {seconds}")

    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)


def get_last_schedule_run(context):
    schedule_name = context.get_tag(key="dagster/schedule_name")
    if schedule_name is not None:
        runs = context.instance.get_run_records(
            filters=RunsFilter(
                statuses=[DagsterRunStatus.SUCCESS],
                job_name=context.job_name,
                tags={"dagster/schedule_name": schedule_name},
            ),
            limit=1,
        )

        last_run = runs[0] if runs else None
        if last_run is not None:
            return last_run.create_timestamp.astimezone(tz=LOCAL_TIME_ZONE)
        else:
            return None
    else:
        # pass if ad hoc query
        return None
