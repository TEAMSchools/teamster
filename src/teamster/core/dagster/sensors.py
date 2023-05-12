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

    context.log.debug(context.dagster_event)
    context.log.debug(context.dagster_run)

    for event in step_failure_events:
        run_id = event.logging_tags["run_id"]

        run_record = context.instance.get_run_record_by_id(run_id)
        context.log.info(
            (
                f"{event.event_specific_data.error_source} "
                f"[{run_id}] {event.asset_key.to_user_string()}: "
                f"{event.job_name}/{event.step_key} "
                f"{run_record.end_time}"
            )
        )

        if event.event_specific_data.error_source in [
            ErrorSource.FRAMEWORK_ERROR,
            ErrorSource.INTERRUPT,
            ErrorSource.UNEXPECTED_ERROR,
        ]:
            if run_record.end_time > last_tick.timestamp():
                result = client._execute(
                    query=LAUNCH_RUN_REEXECUTION_QUERY,
                    variables={"parentRunId": run_id},
                )

                context.log.info(result)


# DagsterEvent(
#     event_type_value="PIPELINE_FAILURE",
#     job_name="__ASSET_JOB_31",
#     step_handle=None,
#     node_handle=None,
#     step_kind_value=None,
#     logging_tags={},
#     event_specific_data=JobFailureData(
#         error=SerializableErrorInfo(
#             message="dagster._core.errors.DagsterExecutionInterruptedError: Execut...,
#             stack=[
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/...',
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/...',
#                 '  File "/usr/local/lib/python3.10/site-packages/dagster/_core/...',
#             ],
#             cls_name="DagsterExecutionInterruptedError",
#             cause=None,
#             context=None,
#         )
#     ),
#     message='Execution of run for "__ASSET_JOB_31" failed. Execution was interrup...',
#     pid=1,
#     step_key=None,
# )


# RunRecord(
#     storage_id=15819666,
#     dagster_run=DagsterRun(
#         job_name="__ASSET_JOB_49",
#         run_id="120f7b6a-d6b3-4c8d-b17f-0981108852c1",
#         run_config={},
#         asset_selection=frozenset(
#             {AssetKey(["kippnewark", "dbt", "deanslist", "src_deanslist__behavior"])}
#         ),
#         solid_selection=None,
#         solids_to_execute=None,
#         step_keys_to_execute=None,
#         status="DagsterRunStatus.FAILURE:< 'FAILURE'>",
#         tags={
#             ".dagster/agent_type": "HYBRID",
#             "dagster/agent_id": "949fbff1-dbf6-458a-936c-d7425e450d6a",
#             "dagster/auto_materialize": "true",
#             "dagster/git_commit_hash": "a5319afdc17a7e84d0ca4a3b40a474c45cfa165a",
#             "dagster/git_project_url": "https://github.com/TEAMSchools/teamster/t...",
#             "dagster/image": "us-central1-docker.pkg.dev/teamster-332318/...",
#             "dagster/partition": "2023-05-12|125",
#             "dagster/partition/date": "2023-05-12",
#             "dagster/partition/school": "125",
#         },
#         root_run_id=None,
#         parent_run_id=None,
#         job_snapshot_id="c1f018c88594925ed6aaf8587849ea187572031a",
#         execution_plan_snapshot_id="3b6c7a8d21ac6cae30ce753b2aed1538283cce5e",
#         external_job_origin=ExternalJobOrigin(
#             external_repository_origin=ExternalRepositoryOrigin(
#                 code_location_origin=RegisteredCodeLocationOrigin(
#                     location_name="kippnewark"
#                 ),
#                 repository_name="__repository__",
#             ),
#             job_name="__ASSET_JOB_49",
#         ),
#         job_code_origin=JobPythonOrigin(
#             job_name="__ASSET_JOB_49",
#             repository_origin=RepositoryPythonOrigin(
#                 executable_path="/usr/local/bin/python",
#                 code_pointer=ModuleCodePointer(
#                     module="teamster.kippnewark.definitions",
#                     fn_name="defs",
#                     working_directory="/root/app",
#                 ),
#                 container_image="us-central1-docker.pkg.dev/teamster-332318/...",
#                 entry_point=["dagster"],
#                 container_context={
#                     "env_vars": [
#                         "DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT=0",
#                         "DAGSTER_CLOUD_DEPLOYMENT_NAME=prod",
#                         "DAGSTER_CLOUD_LOCATION_NAME=kippnewark",
#                     ],
#                     "k8s": {
#                         "env_secrets": [
#                             "kippnewark-edplan-sftp-password",
#                             "kippnewark-edplan-sftp-username",
#                             "kippnewark-ps-db-password",
#                             "kippnewark-ps-db-version",
#                             "kippnewark-ps-ssh-host",
#                             "kippnewark-ps-ssh-password",
#                             "kippnewark-ps-ssh-port",
#                             "kippnewark-ps-ssh-remote-bind-host",
#                             "kippnewark-ps-ssh-username",
#                             "kippnewark-titan-sftp-password",
#                             "kippnewark-titan-sftp-username",
#                             "mssql-database",
#                             "mssql-host",
#                             "mssql-password",
#                             "mssql-port",
#                             "mssql-username",
#                             "nps-sftp-host",
#                             "nps-sftp-password",
#                             "nps-sftp-username",
#                             "pythonanywhere-sftp-host",
#                             "pythonanywhere-sftp-password",
#                             "pythonanywhere-sftp-username",
#                         ],
#                         "volume_mounts": [
#                             {
#                                 "mountPath": "/etc/secret-volume",
#                                 "name": "secret-volume",
#                                 "readOnly": True,
#                             }
#                         ],
#                         "volumes": [
#                             {
#                                 "name": "secret-volume",
#                                 "secret": {"secretName": "secret-files"},
#                             }
#                         ],
#                     },
#                 },
#             ),
#         ),
#         has_repository_load_data=False,
#     ),
#     create_timestamp=datetime.datetime(
#         2023, 5, 12, 4, 24, 27, 33018, tzinfo=datetime.timezone.utc
#     ),
#     update_timestamp=datetime.datetime(
#         2023, 5, 12, 4, 33, 0, 682953, tzinfo=datetime.timezone.utc
#     ),
#     start_time=1683865838.494449,
#     end_time=1683865980.683595,
# )
