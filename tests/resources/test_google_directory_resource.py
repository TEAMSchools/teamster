import json

from dagster import build_resources

from teamster.libraries.google.directory.resources import GoogleDirectoryResource

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


def test_list_orgunits():
    data = DIRECTORY.list_orgunits(org_unit_type="all")

    with open(file="env/orgunits.json", mode="w") as f:
        json.dump([data], f)


def test_get_orgunit():
    data = DIRECTORY.get_orgunit(org_unit_path="")
    print(data)


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


def test_batch_insert_users():
    DIRECTORY.batch_insert_users(
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
    DIRECTORY.batch_update_users(
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

    DIRECTORY.batch_update_users(
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
    DIRECTORY.batch_insert_members(
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
    DIRECTORY.batch_insert_role_assignments(
        [
            {
                "assignedTo": "102120740905198094274",
                "roleId": "6403551156764679",
                "scopeType": "ORG_UNIT",
                "orgUnitId": "01km0r9l4dd2g7e",  # Service Accounts
            }
        ]
    )
