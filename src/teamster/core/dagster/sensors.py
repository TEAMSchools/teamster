import json
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
    cursor: dict = json.loads(context.cursor or "{}")

    update_timestamp = pendulum.from_format(
        string=(cursor.get("update_timestamp") or "1970-01-01T00:00:00.000000+00:000"),
        fmt="YYYY-MM-DD[T]HH:mm:ss.SSSSSSZ",
    )

    dagster_cloud_org_name = os.getenv("DAGSTER_CLOUD_AGENT_TOKEN").split(":")[1]
    dagster_cloud_hostname = f"https://{dagster_cloud_org_name}.dagster.cloud/prod"

    client = DagsterGraphQLClient(
        hostname=dagster_cloud_hostname,
        transport=RequestsHTTPTransport(
            url=f"{dagster_cloud_hostname}/graphql",
            headers={"Dagster-Cloud-Api-Token": os.getenv("DAGSTER_CLOUD_USER_TOKEN")},
        ),
    )

    for event in context.get_step_failure_events():
        if event.event_specific_data.error_source == ErrorSource.INTERRUPT:
            context.log.info(event)

            run_id = event.logging_tags["run_id"]

            run_record = context.instance.get_run_record_by_id(run_id)
            context.log.debug(run_record)

            # result = client._execute(
            #     query=LAUNCH_RUN_REEXECUTION_QUERY, variables={"parentRunId": run_id}
            # )

            # context.log.info(result)


# DagsterEvent(
#     event_type_value='STEP_FAILURE',
#     job_name='__ASSET_JOB_2',
#     step_handle=StepHandle(
#         node_handle=NodeHandle(
#             name='kipptaf__dbt__alchemer__src_alchemer__survey_response',
#             parent=None
#         ),
#         key='kipptaf__dbt__alchemer__src_alchemer__survey_response'
#     ),
#     node_handle=NodeHandle(
#         name='kipptaf__dbt__alchemer__src_alchemer__survey_response',
#         parent=None
#     ),
#     step_kind_value='COMPUTE',
#     logging_tags={
#         'job_name': '__ASSET_JOB_2',
#         'op_name': 'kipptaf__dbt__alchemer__src_alchemer__survey_response',
#         'resource_fn_name': 'None',
#         'resource_name': 'None',
#         'run_id': '35b4f2b7-77fe-4a26-9087-9818f2f237a1',
#         'step_key': 'kipptaf__dbt__alchemer__src_alchemer__survey_response'
#     },
#     event_specific_data=StepFailureData(
#         error=SerializableErrorInfo(
#             message='dagster._core.errors.DagsterExecutionInterruptedError\n',
#             stack=[
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/...',
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/...',
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/...',
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/...',
#                 '  File "/usr/local/lib/python3.10/contextlib.py", line 135, in ...',
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/...',
#                 '  File "/usr/local/lib/python3.10/contextlib.py", line 135, in ...',
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/er...',
#                 '  File "/usr/local/lib/python3.10/contextlib.py", line 135, in ...',
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_utils/...'
#             ],
#             cls_name='DagsterExecutionInterruptedError',
#             cause=None,
#             context=None
#         ),
#         user_failure_data=None,
#         error_source=<ErrorSource.INTERRUPT: 'INTERRUPT'>
#     ),
#     message='Execution of step "kipptaf__dbt__alchemer__src_alchemer__survey_resp...',
#     pid=1,
#     step_key='kipptaf__dbt__alchemer__src_alchemer__survey_response'
# )
