import json

from dagster import build_resources

from teamster.core.google.directory.resources import GoogleDirectoryResource


def test_resource():
    with build_resources(
        resources={
            "directory": GoogleDirectoryResource(
                customer_id="C029u7m0n",
                service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
                delegated_account="dagster@apps.teamschools.org",
            )
        }
    ) as resources:
        directory: GoogleDirectoryResource = resources.directory

    users = directory.list_users()

    with open(file="env/users.json", mode="w") as f:
        json.dump(users, f)
