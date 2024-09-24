from dagster import OpExecutionContext, op
from dagster_slack import SlackResource

from teamster.libraries.google.directory.resources import GoogleDirectoryResource


@op
def google_directory_user_create_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    slack: SlackResource,
    users,
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

    if exceptions:
        exceptions.insert(0, "*`google_directory_user_create_op` errors:*")

        slack_client = slack.get_client()

        slack_client.chat_postMessage(
            channel="#dagster-alerts", text="\n".join(exceptions)
        )

    return members


@op
def google_directory_member_create_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    slack: SlackResource,
    members,
):
    context.log.info(f"Adding {len(members)} members to groups")

    exceptions = google_directory.batch_insert_members(members)

    if exceptions:
        exceptions.insert(0, "*`google_directory_member_create_op` errors:*")

        slack_client = slack.get_client()

        slack_client.chat_postMessage(
            channel="#dagster-alerts", text="\n".join(exceptions)
        )


@op
def google_directory_user_update_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    slack: SlackResource,
    users,
):
    update_users = [u for u in users if u["is_update"]]
    context.log.info(f"Updating {len(update_users)} users")

    exceptions = google_directory.batch_update_users(update_users)

    if google_directory._exceptions:
        exceptions.insert(0, "*`google_directory_user_update_op` errors:*")

        slack_client = slack.get_client()

        slack_client.chat_postMessage(
            channel="#dagster-alerts", text="\n".join(exceptions)
        )


@op
def google_directory_role_assignment_create_op(
    context: OpExecutionContext,
    google_directory: GoogleDirectoryResource,
    slack: SlackResource,
    role_assignments,
):
    context.log.info(f"Adding {len(role_assignments)} role assignments")

    exceptions = google_directory.batch_insert_role_assignments(role_assignments)

    if exceptions:
        exceptions.insert(0, "*`google_directory_role_assignment_create_op` errors:*")

        slack_client = slack.get_client()

        slack_client.chat_postMessage(
            channel="#dagster-alerts", text="\n".join(exceptions)
        )
