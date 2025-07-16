import time
from typing import Any

from dagster import ExpectationResult, OpExecutionContext, Output, op

from teamster.core.utils.functions import chunk
from teamster.libraries.zendesk.resources import ZendeskResource


@op
def zendesk_user_sync_op(
    context: OpExecutionContext, zendesk: ZendeskResource, users: list[dict[str, Any]]
):
    chunked_users = chunk(obj=users, size=100)

    running_jobs = []
    failures = []
    jobs_queue = {}

    while True:
        # add job to queue
        if len(running_jobs) == 30:
            context.log.warning("Jobs queue full...")
        else:
            try:
                users_chunk: list[dict] = next(chunked_users)

                payload = [
                    {
                        k: v
                        for k, v in u.items()
                        if k
                        in [
                            "email",
                            "external_id",
                            "name",
                            "suspended",
                            "organization_id",
                            "role",
                            "user_fields",
                            "verified",
                        ]
                    }
                    for u in users_chunk
                ]

                post_response = zendesk.post(
                    resource="users/create_or_update_many", json={"users": payload}
                ).json()

                jobs_queue[post_response["job_status"]["id"]] = post_response[
                    "job_status"
                ]["status"]
            except StopIteration:
                pass

        running_jobs = [
            id
            for id, status in jobs_queue.items()
            if status not in ["completed", "failed"]
        ]

        context.log.info(f"{len(running_jobs)} job(s) running...")

        # check status of jobs in queue
        if running_jobs:
            job_statuses = zendesk.get(
                resource="job_statuses/show_many",
                params={"ids": ",".join(running_jobs)},
            ).json()

            for js in job_statuses["job_statuses"]:
                context.log.debug(
                    f"{js['id']} {js['job_type']}: {js['status']} "
                    f"({js['progress'] or 0}/{js['total']} records)"
                    + (f"\n{js['message']}" if js["message"] else "")
                )
                jobs_queue[js["id"]] = js["status"]

                # capture failures
                if js["status"] == "completed":
                    failures.extend(
                        [r for r in js["results"] if r["status"] == "Failed"]
                    )
                elif js["status"] == "failed":
                    failures.append(js)

        # terminate loop when queue is empty
        if len(running_jobs) == 0:
            break
        else:
            time.sleep(1)

    if failures:
        context.log.error(failures)

    yield Output(value=None)
    yield ExpectationResult(
        success=(len(failures) == 0), metadata={"failures": str(failures)}
    )
