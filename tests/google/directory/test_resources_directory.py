import json

from dagster import build_resources

from teamster.core.google.directory.resources import GoogleDirectoryResource

with build_resources(
    resources={
        "directory": GoogleDirectoryResource(
            customer_id="C029u7m0n",
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
            delegated_account="dagster@apps.teamschools.org",
        )
    }
) as resources:
    DIRECTORY: GoogleDirectoryResource = resources.directory


def test_list_roles():
    data = DIRECTORY.list_roles()

    with open(file="env/roles.json", mode="w") as f:
        json.dump(data, f)


def test_list_role_assignments():
    data = DIRECTORY.list_role_assignments()

    with open(file="env/role_assignments.json", mode="w") as f:
        json.dump(data, f)


def test_list_members():
    data = DIRECTORY.list_members(group_key="group-students-miami@teamstudents.org")

    with open(file="env/members.json", mode="w") as f:
        json.dump(data, f)


def test_list_groups():
    data = DIRECTORY.list_groups()

    with open(file="env/groups.json", mode="w") as f:
        json.dump(data, f)


def test_get_user():
    data = DIRECTORY.get_user(user_key="113203151440162455385")
    print(data)


def test_list_users():
    data = DIRECTORY.list_users(projection="full")

    with open(file="env/users.json", mode="w") as f:
        json.dump(data, f)
