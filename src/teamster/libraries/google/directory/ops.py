from typing import Any

from dagster import ExpectationResult, OpExecutionContext, Output, op

from teamster.libraries.google.directory.resources import GoogleDirectoryResource


@op
def google_directory_user_create_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    users: list[dict[str, Any]],
):
    # create users
    create_users = [u for u in users if u["is_create"]]
    context.log.info(f"Creating {len(create_users)} users")

    exceptions = google_directory.batch_insert_users(create_users)

    # add users to group
    members = [
        {
            "groupKey": u["groupKey"],
            "email": u["primaryEmail"],
            "delivery_settings": "DISABLED",
        }
        for u in create_users
    ]

    yield Output(value=members)
    yield ExpectationResult(
        success=(len(exceptions) == 0), metadata={"exceptions": exceptions}
    )


@op
def google_directory_member_create_op(
    context: OpExecutionContext, google_directory: GoogleDirectoryResource, members
):
    context.log.info(f"Adding {len(members)} members to groups")

    exceptions = google_directory.batch_insert_members(members)

    yield Output(value=None)
    yield ExpectationResult(
        success=(len(exceptions) == 0), metadata={"exceptions": exceptions}
    )


@op
def google_directory_user_update_op(
    context: OpExecutionContext, google_directory: GoogleDirectoryResource, users
):
    update_users = [u for u in users if u["is_update"]]
    context.log.info(f"Updating {len(update_users)} users")

    exceptions = google_directory.batch_update_users(update_users)

    yield Output(value=None)
    yield ExpectationResult(
        success=(len(exceptions) == 0), metadata={"exceptions": exceptions}
    )


@op
def google_directory_role_assignment_create_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    role_assignments,
):
    context.log.info(f"Adding {len(role_assignments)} role assignments")

    exceptions = google_directory.batch_insert_role_assignments(role_assignments)

    yield Output(value=None)
    yield ExpectationResult(
        success=(len(exceptions) == 0), metadata={"exceptions": exceptions}
    )
