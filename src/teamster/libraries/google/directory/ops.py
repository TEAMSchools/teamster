from typing import Any

from dagster import ExpectationResult, OpExecutionContext, Output, op

from teamster.libraries.google.directory.resources import GoogleDirectoryResource


@op
def google_directory_user_create_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    users: list[dict[str, Any]],
):
    """Create new Google Workspace users and return them as group members.

    Filters the input list to records where ``is_create`` is truthy, calls
    ``batch_insert_users``, and yields the created users formatted as member
    dicts for downstream ops.

    Args:
        users: List of user resource dicts. Only records with ``is_create``
            set are processed.
    """
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
        success=(len(exceptions) == 0), metadata={"exceptions": str(exceptions)}
    )


@op
def google_directory_member_create_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    members: list[dict[str, Any]],
):
    """Add members to Google Workspace groups.

    Args:
        members: List of member resource dicts. Each dict must include
            ``groupKey`` and ``email``.
    """
    context.log.info(f"Adding {len(members)} members to groups")

    exceptions = google_directory.batch_insert_members(members)

    yield Output(value=None)
    yield ExpectationResult(
        success=(len(exceptions) == 0), metadata={"exceptions": str(exceptions)}
    )


@op
def google_directory_user_update_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    users: list[dict[str, Any]],
):
    """Update existing Google Workspace users.

    Filters the input list to records where ``is_update`` is truthy before
    calling ``batch_update_users``.

    Args:
        users: List of user resource dicts. Only records with ``is_update``
            set are processed.
    """
    update_users = [u for u in users if u["is_update"]]
    context.log.info(f"Updating {len(update_users)} users")

    exceptions = google_directory.batch_update_users(update_users)

    yield Output(value=None)
    yield ExpectationResult(
        success=(len(exceptions) == 0), metadata={"exceptions": str(exceptions)}
    )


@op
def google_directory_role_assignment_create_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    role_assignments: list[dict[str, Any]],
):
    """Create Google Workspace role assignments.

    Args:
        role_assignments: List of role assignment resource dicts.
    """
    context.log.info(f"Adding {len(role_assignments)} role assignments")

    exceptions = google_directory.batch_insert_role_assignments(role_assignments)

    yield Output(value=None)
    yield ExpectationResult(
        success=(len(exceptions) == 0), metadata={"exceptions": str(exceptions)}
    )
