import os

import pendulum
from dagster import (
    DagsterEventType,
    EventRecordsFilter,
    RunFailureSensorContext,
    run_failure_sensor,
)
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
        event_records = [
            context.instance.get_event_records(
                event_records_filter=EventRecordsFilter(
                    event_type=DagsterEventType.ENGINE_EVENT,
                    asset_key=asset_key,
                    asset_partitions=[context.dagster_run.tags["dagster/partition"]],
                )
            )
            for asset_key in context.dagster_run.asset_selection
        ]
        context.log.debug(event_records)

        context.log.info(
            "\n".join(
                [
                    run_id,
                    str(run_record.end_time),
                    context.failure_event.event_type_value,
                    context.failure_event.message,
                    str(context.dagster_run.asset_selection),
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
                    str(run_record.end_time),
                    str(event.event_specific_data.error_source),
                    event.message,
                    str(event.asset_key),
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


# DagsterRun(
#     job_name="...",
#     run_id="...",
#     run_config={},
#     asset_selection=frozenset(
#         {
#             AssetKey(
#                 [
#                     "...",
#                 ]
#             )
#         }
#     ),
#     solid_selection=None,
#     solids_to_execute=None,
#     step_keys_to_execute=None,
#     status="<DagsterRunStatus.FAILURE: 'FAILURE'>",
#     tags={
#         ".dagster/agent_type": "HYBRID",
#         "dagster/agent_id": "...",
#         "dagster/git_commit_hash": "...",
#         "dagster/git_project_url": "...",
#         "dagster/image": "...",
#         "dagster/partition": "...",
#         "dagster/partition_set": "...",
#         "dagster/run_key": "...",
#         "dagster/sensor_name": "...",
#     },
#     root_run_id=None,
#     parent_run_id=None,
#     job_snapshot_id="...",
#     execution_plan_snapshot_id="...",
#     external_job_origin=ExternalJobOrigin(
#         external_repository_origin=ExternalRepositoryOrigin(
#             code_location_origin=RegisteredCodeLocationOrigin(location_name="..."),
#             repository_name="...",
#         ),
#         job_name="...",
#     ),
#     job_code_origin=JobPythonOrigin(
#         job_name="...",
#         repository_origin=RepositoryPythonOrigin(
#             executable_path="...",
#             code_pointer=ModuleCodePointer(
#                 module="...",
#                 fn_name="...",
#                 working_directory="...",
#             ),
#             container_image="...",
#             entry_point=["..."],
#             container_context={
#                 "env_vars": [
#                     "...",
#                 ],
#                 "k8s": {
#                     "env_secrets": [
#                         "...",
#                     ],
#                     "volume_mounts": [
#                         {
#                             "mountPath": "...",
#                             "name": "...",
#                             "readOnly": True,
#                         }
#                     ],
#                     "volumes": [
#                         {
#                             "name": "...",
#                             "secret": {"secretName": "..."},
#                         }
#                     ],
#                 },
#             },
#         ),
#     ),
#     has_repository_load_data=False,
# )

# DagsterEvent(
#     event_type_value="PIPELINE_FAILURE",
#     job_name="...",
#     step_handle=None,
#     node_handle=None,
#     step_kind_value=None,
#     logging_tags={},
#     event_specific_data=JobFailureData(
#         error=SerializableErrorInfo(
#             message="...",
#             stack=[
#                 "...",
#             ],
#             cls_name="DagsterExecutionInterruptedError",
#             cause=None,
#             context=None,
#         )
#     ),
#     message="...",
#     pid=1,
#     step_key=None,
# )

# RunRecord(
#     storage_id=16205600,
#     dagster_run=DagsterRun(
#         job_name="...",
#         run_id="...",
#         run_config={},
#         asset_selection=frozenset(
#             {
#                 AssetKey(
#                     [
#                         "...",
#                     ]
#                 )
#             }
#         ),
#         solid_selection=None,
#         solids_to_execute=None,
#         step_keys_to_execute=None,
#         status="<DagsterRunStatus.FAILURE: 'FAILURE'>",
#         tags={
#             ".dagster/agent_type": "HYBRID",
#             "dagster/agent_id": "...",
#             "dagster/git_commit_hash": "...",
#             "dagster/git_project_url": "...",
#             "dagster/image": "...",
#             "dagster/partition": "...",
#             "dagster/partition_set": "...",
#             "dagster/run_key": "...",
#             "dagster/sensor_name": "...",
#         },
#         root_run_id=None,
#         parent_run_id=None,
#         job_snapshot_id="...",
#         execution_plan_snapshot_id="...",
#         external_job_origin=ExternalJobOrigin(
#             external_repository_origin=ExternalRepositoryOrigin(
#                 code_location_origin=RegisteredCodeLocationOrigin(
#                     location_name="..."
#                 ),
#                 repository_name="...",
#             ),
#             job_name="...",
#         ),
#         job_code_origin=JobPythonOrigin(
#             job_name="...",
#             repository_origin=RepositoryPythonOrigin(
#                 executable_path="...",
#                 code_pointer=ModuleCodePointer(
#                     module="...",
#                     fn_name="...",
#                     working_directory="...",
#                 ),
#                 container_image="...",
#                 entry_point=["..."],
#                 container_context={
#                     "env_vars": [
#                         "...",
#                     ],
#                     "k8s": {
#                         "env_secrets": [
#                             "...",
#                         ],
#                         "volume_mounts": [
#                             {
#                                 "mountPath": "...",
#                                 "name": "...",
#                                 "readOnly": True,
#                             }
#                         ],
#                         "volumes": [
#                             {
#                                 "name": "...",
#                                 "secret": {"secretName": "..."},
#                             }
#                         ],
#                     },
#                 },
#             ),
#         ),
#         has_repository_load_data=False,
#     ),
#     create_timestamp=datetime.datetime(
#         2023, 5, 15, 14, 40, 32, 414947, tzinfo=datetime.timezone.utc
#     ),
#     update_timestamp=datetime.datetime(
#         2023, 5, 15, 14, 45, 13, 248971, tzinfo=datetime.timezone.utc
#     ),
#     start_time=1684161882.688826,
#     end_time=1684161913.250036,
# )
