import os

import pendulum
from dagster import RunFailureSensorContext, run_failure_sensor
from dagster._core.execution.plan.objects import ErrorSource
from dagster_graphql import DagsterGraphQLClient
from gql.transport.requests import RequestsHTTPTransport

LAUNCH_RUN_REEXECUTION_QUERY = """
mutation($parentRunId: String!) {
  launchRunReexecution(
    reexecutionParams: { parentRunId: $parentRunId, strategy: FROM_FAILURE }
  ) {
    __typename
    ... on PythonError {
      message
      className
      stack
    }
  }
}
"""


@run_failure_sensor
def run_execution_interrupted_sensor(context: RunFailureSensorContext):
    # sensor context doesn't have cursor: hardcode to sensor tick interval
    last_tick = pendulum.now().subtract(seconds=30)
    context.log.debug(last_tick)

    dagster_cloud_hostname = (
        "https://"
        + os.getenv("DAGSTER_CLOUD_AGENT_TOKEN").split(":")[1]
        + ".dagster.cloud/prod"
    )

    client = DagsterGraphQLClient(
        hostname=dagster_cloud_hostname,
        transport=RequestsHTTPTransport(
            url=f"{dagster_cloud_hostname}/graphql",
            headers={"Dagster-Cloud-Api-Token": os.getenv("DAGSTER_CLOUD_USER_TOKEN")},
        ),
    )

    step_failure_events = context.get_step_failure_events()

    if not step_failure_events:
        run_id = context.dagster_run.run_id

        run_record = context.instance.get_run_record_by_id(run_id)
        context.log.info(
            "\n".join(
                [
                    run_id,
                    run_record.end_time,
                    context.failure_event.event_type_value,
                    context.failure_event.message,
                    context.dagster_run.asset_selection,
                    context.dagster_run.job_name,
                ]
            )
        )

        if context.failure_event.event_type_value == "PIPELINE_FAILURE":
            result = client._execute(
                query=LAUNCH_RUN_REEXECUTION_QUERY, variables={"parentRunId": run_id}
            )

            context.log.info(result)

    for event in step_failure_events:
        run_id = event.logging_tags["run_id"]

        run_record = context.instance.get_run_record_by_id(run_id)
        context.log.info(
            "\n".join(
                [
                    run_id,
                    run_record.end_time,
                    event.event_specific_data.error_source,
                    event.message,
                    event.asset_key,
                    event.job_name,
                    event.step_key,
                ]
            )
        )

        if event.event_specific_data.error_source in [
            ErrorSource.FRAMEWORK_ERROR,
            ErrorSource.INTERRUPT,
            ErrorSource.UNEXPECTED_ERROR,
        ]:
            result = client._execute(
                query=LAUNCH_RUN_REEXECUTION_QUERY, variables={"parentRunId": run_id}
            )

            context.log.info(result)
