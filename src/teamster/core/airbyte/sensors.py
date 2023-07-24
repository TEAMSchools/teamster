# import sys
# from typing import Dict, List, cast

# import pendulum
# from dagster import Failure, SensorEvaluationContext
# from dagster_airbyte import AirbyteCloudResource, AirbyteState


# def _sensor(context: SensorEvaluationContext, airbyte: AirbyteCloudResource):
#     if context.cursor is not None:
#         last_checked = pendulum.from_timestamp(timestamp=context.cursor)
#     else:
#         last_checked = pendulum.from_timestamp(timestamp=0)

#     jobs = airbyte.make_request(
#         endpoint="/jobs",
#         data={"updatedAtStart": last_checked.format("YYYY-MM-DDTHH:mm:sszz")},
#         method="GET",
#     )

#     job_details = airbyte.get_job_status(connection_id, job_id)

#     attempts = cast(List, job_details.get("attempts", []))

#     cur_attempt = len(attempts)

#     # spit out the available Airbyte log info
#     if cur_attempt:
#         if airbyte._should_forward_logs:
#             log_lines = attempts[logged_attempts].get("logs", {}).get("logLines", [])

#             for line in log_lines[logged_lines:]:
#                 sys.stdout.write(line + "\n")
#                 sys.stdout.flush()
#             logged_lines = len(log_lines)

#         # if there's a next attempt, this one will have no more log messages
#         if logged_attempts < cur_attempt - 1:
#             logged_lines = 0
#             logged_attempts += 1

#     job_info = cast(Dict[str, object], job_details.get("job", {}))

#     state = job_info.get("status")

#     if state in (AirbyteState.RUNNING, AirbyteState.PENDING, AirbyteState.INCOMPLETE):
#         # continue
#         ...
#     elif state == AirbyteState.SUCCEEDED:
#         # break
#         ...
#     elif state == AirbyteState.ERROR:
#         raise Failure(f"Job failed: {job_id}")
#     elif state == AirbyteState.CANCELLED:
#         raise Failure(f"Job was cancelled: {job_id}")
#     else:
#         raise Failure(f"Encountered unexpected state `{state}` for job_id {job_id}")
