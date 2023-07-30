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


def test_get_user():
    user = DIRECTORY.get_user(user_key="113203151440162455385")
    print(user)


def test_list_users():
    users = DIRECTORY.list_users(projection="full")

    with open(file="env/users.json", mode="w") as f:
        json.dump(users, f)
