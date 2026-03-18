import json
from unittest.mock import MagicMock, patch

import httplib2
from dagster import EnvVar, build_resources
from googleapiclient.errors import HttpError

from teamster.libraries.google.directory.resources import GoogleDirectoryResource


def test_list_retries_on_503_mid_pagination():
    resource = GoogleDirectoryResource(customer_id="C123")
    resource._log = MagicMock()

    mock_resource = MagicMock()
    resource._resource = mock_resource

    http_error = HttpError(
        resp=httplib2.Response({"status": "503"}),
        content=b"Service Unavailable",
    )
    mock_execute = mock_resource.users.return_value.list.return_value.execute
    mock_execute.side_effect = [
        {"users": [{"id": "u1"}], "nextPageToken": "token1"},
        http_error,
        {"users": [{"id": "u2"}]},
    ]

    with patch("dagster._utils.backoff.time.sleep"):
        data = resource._list("users", customer="C123")

    assert data == [{"id": "u1"}, {"id": "u2"}]
    assert mock_execute.call_count == 3


def get_google_directory_resource() -> GoogleDirectoryResource:
    with build_resources(
        resources={
            "directory": GoogleDirectoryResource(
                customer_id=EnvVar("GOOGLE_WORKSPACE_CUSTOMER_ID"),
                delegated_account=EnvVar("GOOGLE_DIRECTORY_DELEGATED_ACCOUNT"),
                # service_account_file_path=(
                #     "/etc/secret-volume/gcloud_dagster_service_account.json"
                # ),
            )
        }
    ) as resources:
        return resources.directory


def test_list_orgunits():
    google_directory = get_google_directory_resource()

    data = google_directory.list_orgunits(org_unit_type="all")

    with open(file="env/orgunits.json", mode="w") as f:
        json.dump([data], f)


def test_get_orgunit():
    google_directory = get_google_directory_resource()

    data = google_directory.get_orgunit(org_unit_path="")

    with open(file="env/org_unit.json", mode="w") as f:
        json.dump(data, f)


def test_list_roles():
    google_directory = get_google_directory_resource()

    data = google_directory.list_roles()

    with open(file="env/roles.json", mode="w") as f:
        json.dump(data, f)


def test_list_role_assignments():
    google_directory = get_google_directory_resource()

    data = google_directory.list_role_assignments()

    with open(file="env/role_assignments.json", mode="w") as f:
        json.dump(data, f)


def test_list_members():
    google_directory = get_google_directory_resource()

    data = google_directory.list_members(
        group_key="group-students-miami@teamstudents.org"
    )

    with open(file="env/members.json", mode="w") as f:
        json.dump(data, f)


def test_list_groups():
    google_directory = get_google_directory_resource()

    data = google_directory.list_groups()

    with open(file="env/groups.json", mode="w") as f:
        json.dump(data, f)


def test_get_user():
    user_key = "113203151440162455385"

    google_directory = get_google_directory_resource()

    data = google_directory.get_user(user_key=user_key)

    with open(file=f"env/user_{user_key}.json", mode="w") as f:
        json.dump(data, f)


def test_list_users():
    google_directory = get_google_directory_resource()

    data = google_directory.list_users(projection="full")

    with open(file="env/users.json", mode="w") as f:
        json.dump(data, f)


def test_batch_insert_users():
    google_directory = get_google_directory_resource()

    google_directory.batch_insert_users(
        [
            {
                "primaryEmail": "datarobot_test_1@apps.teamschools.org",
                "name": {"givenName": "Terius", "familyName": "Gray"},
                "orgUnitPath": "/Service Accounts/Test",
                "password": "5c69881e9835ae7f5eb11f4cc26f0a0085509bdb",  # gitleaks:allow
                "hashFunction": "SHA-1",
                "changePasswordAtNextLogin": False,
                "suspended": True,
            },
            {
                "primaryEmail": "datarobot_test_2@apps.teamschools.org",
                "name": {"givenName": "Byron", "familyName": "Thomas"},
                "orgUnitPath": "/Service Accounts/Test",
                "password": "5c69881e9835ae7f5eb11f4cc26f0a0085509bdb",  # gitleaks:allow
                "hashFunction": "SHA-1",
                "changePasswordAtNextLogin": False,
                "suspended": True,
            },
        ]
    )


def test_batch_update_users():
    google_directory = get_google_directory_resource()

    google_directory.batch_update_users(
        [
            {
                "primaryEmail": "datarobot_test_1@apps.teamschools.org",
                "suspended": False,
                "orgUnitPath": "/Service Accounts",
                "name": {"givenName": "Juvenile"},
            },
            {
                "primaryEmail": "datarobot_test_2@apps.teamschools.org",
                "suspended": False,
                "orgUnitPath": "/Service Accounts",
                "name": {"givenName": "Manny", "familyName": "Fresh"},
            },
        ]
    )

    google_directory.batch_update_users(
        [
            {
                "primaryEmail": "datarobot_test_1@apps.teamschools.org",
                "suspended": True,
                "orgUnitPath": "/Service Accounts/Test",
                "name": {"givenName": "Terius", "familyName": "Gray"},
            },
            {
                "primaryEmail": "datarobot_test_2@apps.teamschools.org",
                "suspended": True,
                "orgUnitPath": "/Service Accounts/Test",
                "name": {"givenName": "Byron", "familyName": "Thomas"},
            },
        ]
    )


def test_batch_insert_members():
    google_directory = get_google_directory_resource()

    google_directory.batch_insert_members(
        [
            {
                "groupKey": "datatest@apps.teamschools.org",
                "email": "datarobot_test_1@apps.teamschools.org",
                "delivery_settings": "DISABLED",
            },
            {
                "groupKey": "datatest@apps.teamschools.org",
                "email": "datarobot_test_2@apps.teamschools.org",
                "delivery_settings": "DISABLED",
            },
        ]
    )


def test_batch_insert_role_assignments():
    google_directory = get_google_directory_resource()

    google_directory.batch_insert_role_assignments(
        [
            {
                "assignedTo": "102120740905198094274",
                "roleId": "6403551156764679",
                "scopeType": "ORG_UNIT",
                "orgUnitId": "01km0r9l4dd2g7e",  # Service Accounts
            }
        ]
    )
