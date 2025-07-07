import time

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetExecutionContext,
    Output,
    asset,
)
from dagster_gcp import BigQueryResource

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.core.utils.functions import chunk
from teamster.libraries.zendesk.resources import ZendeskResource

asset_key = [CODE_LOCATION, "zendesk", "user_sync"]


@asset(
    key=asset_key,
    check_specs=[AssetCheckSpec(name="zero_api_errors", asset=asset_key)],
    group_name="zendesk",
    kinds={"python"},
)
def zendesk_user_sync(
    context: AssetExecutionContext,
    db_bigquery: BigQueryResource,
    zendesk: ZendeskResource,
):
    query = "select * from kipptaf_extracts.rpt_zendesk__users"
    running_jobs = []
    errors = []
    jobs_queue = {}

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")
    chunked_users = chunk(obj=arrow.to_pylist(), size=100)

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

                # capture errors
                if js["status"] == "completed":
                    for r in js["results"]:
                        if r["status"] == "Failed":
                            context.log.error(msg=r)
                            errors.append(r)
                elif js["status"] == "failed":
                    context.log.error(msg=js)
                    errors.append(js)

        # terminate loop when queue is empty
        if len(running_jobs) == 0:
            break
        else:
            time.sleep(1)

    yield Output(value=None)
    yield AssetCheckResult(
        passed=(len(errors) == 0),
        asset_key=context.asset_key,
        check_name="zero_api_errors",
        metadata={"errors": str(errors)},
        severity=AssetCheckSeverity.WARN,
    )


assets = [
    zendesk_user_sync,
]
