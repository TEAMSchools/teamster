import datetime
import decimal
import json
import os
import signal
from contextlib import contextmanager
from zoneinfo import ZoneInfo

from dagster._core.storage.pipeline_run import DagsterRunStatus, RunsFilter

LOCAL_TIME_ZONE = ZoneInfo(os.getenv("LOCAL_TIME_ZONE"))
NOW = datetime.datetime.now(tz=LOCAL_TIME_ZONE)
TODAY = TODAY = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
YESTERDAY = TODAY - datetime.timedelta(days=1)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime.timedelta, decimal.Decimal)):
            return str(o)
        elif isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        else:
            return super().default(o)


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
    if schedule_name:
        runs = context.instance.get_run_records(
            filters=RunsFilter(
                statuses=[DagsterRunStatus.SUCCESS],
                job_name=context.job_name,
                tags={"dagster/schedule_name": schedule_name},
            ),
            limit=1,
        )

        if "resync" not in context.job_name:
            ix = context.job_name.index("_")
            repo_name = context.job_name[:ix]
            resyncs = context.instance.get_run_records(
                filters=RunsFilter(
                    statuses=[DagsterRunStatus.SUCCESS],
                    job_name=f"{repo_name}_resync",
                ),
                limit=1,
            )

        last_run = runs[0] if runs else None
        last_resync = resyncs[0] if resyncs else None
        if last_run is not None:
            return last_run.create_timestamp.astimezone(tz=LOCAL_TIME_ZONE)
        elif last_resync is not None:
            return last_resync.create_timestamp.astimezone(tz=LOCAL_TIME_ZONE)
        else:
            return None
    else:
        # pass if ad hoc query
        return None
