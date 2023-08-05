from dagster import OpExecutionContext, op

from teamster.core.google.directory.resources import GoogleDirectoryResource


@op
def google_directory_user_create_op(
    context: OpExecutionContext, google_directory: GoogleDirectoryResource, users
):
    # create users
    create_users = [u for u in users if u["is_create"]]

    google_directory.batch_insert_users(create_users)

    # add users to group
    members = [
        {
            "groupKey": u["group_key"],
            "email": u["primaryEmail"],
            "delivery_settings": "DISABLED",
        }
        for u in create_users
    ]

    google_directory.batch_insert_members(members)


@op
def google_directory_user_update_op(
    context: OpExecutionContext, google_directory: GoogleDirectoryResource, users
):
    update_users = [u for u in users if u["is_update"]]

    google_directory.batch_update_users(update_users)
