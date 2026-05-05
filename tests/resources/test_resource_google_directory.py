import json
from unittest.mock import MagicMock, patch

import httplib2
import pytest
from dagster import EnvVar, build_resources
from googleapiclient.errors import HttpError

from teamster.libraries.google.directory.resources import (
    GoogleDirectoryResource,
    _retryable_execute,
    _TransientHttpError,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_resource(
    customer_id: str = "C123",
) -> tuple[GoogleDirectoryResource, MagicMock]:
    """Return a resource with its internal API client swapped for a MagicMock."""
    resource = GoogleDirectoryResource(customer_id=customer_id)
    resource._log = MagicMock()
    mock_api = MagicMock()
    resource._resource = mock_api
    return resource, mock_api


def _http_error(status: int, content: bytes = b"error") -> HttpError:
    return HttpError(resp=httplib2.Response({"status": str(status)}), content=content)


def _make_batch_side_effect(responses_per_batch: list[list[tuple]]):
    """Return a side_effect for ``new_batch_http_request``.

    Each inner list contains ``(response, exception)`` tuples that will be
    forwarded to the registered callback when ``execute()`` is called for
    that batch.
    """
    batch_idx = [-1]

    def new_batch(callback):
        batch_idx[0] += 1
        batch_responses = responses_per_batch[batch_idx[0]]
        mock_batch = MagicMock()

        def execute():
            for i, (response, exception) in enumerate(batch_responses):
                callback(str(i + 1), response, exception)

        mock_batch.execute.side_effect = execute
        return mock_batch

    return new_batch


# ── _retryable_execute ────────────────────────────────────────────────────────


def test_retryable_execute_returns_response_on_success():
    mock_request = MagicMock()
    mock_request.execute.return_value = {"kind": "admin#directory#user"}
    assert _retryable_execute(mock_request)() == {"kind": "admin#directory#user"}


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_execute_wraps_transient_codes_as_TransientHttpError(status: int):
    mock_request = MagicMock()
    mock_request.execute.side_effect = _http_error(status)
    with pytest.raises(_TransientHttpError):
        _retryable_execute(mock_request)()


def test_retryable_execute_does_not_wrap_client_error():
    mock_request = MagicMock()
    mock_request.execute.side_effect = _http_error(404)
    with pytest.raises(HttpError) as exc_info:
        _retryable_execute(mock_request)()
    assert type(exc_info.value) is HttpError  # not a _TransientHttpError subclass


# ── _list ─────────────────────────────────────────────────────────────────────


def test_list_retries_on_503_mid_pagination():
    resource, mock_api = _make_resource()
    mock_execute = mock_api.users.return_value.list.return_value.execute
    mock_execute.side_effect = [
        {"users": [{"id": "u1"}], "nextPageToken": "token1"},
        _http_error(503),
        {"users": [{"id": "u2"}]},
    ]

    with patch("dagster._utils.backoff.time.sleep"):
        data = resource._list("users", customer="C123")

    assert data == [{"id": "u1"}, {"id": "u2"}]
    assert mock_execute.call_count == 3


def test_list_returns_single_page():
    resource, mock_api = _make_resource()
    mock_api.users.return_value.list.return_value.execute.return_value = {
        "users": [{"id": "u1"}, {"id": "u2"}]
    }
    assert resource._list("users", customer="C123") == [{"id": "u1"}, {"id": "u2"}]


def test_list_concatenates_multiple_pages():
    resource, mock_api = _make_resource()
    mock_api.users.return_value.list.return_value.execute.side_effect = [
        {"users": [{"id": "u1"}], "nextPageToken": "tok1"},
        {"users": [{"id": "u2"}]},
    ]
    assert resource._list("users", customer="C123") == [{"id": "u1"}, {"id": "u2"}]


def test_list_uses_custom_response_data_key():
    resource, mock_api = _make_resource()
    mock_api.roles.return_value.list.return_value.execute.return_value = {
        "items": [{"roleId": "r1"}]
    }
    data = resource._list("roles", customer="C123", response_data_key="items")
    assert data == [{"roleId": "r1"}]


def test_list_raises_immediately_on_4xx():
    resource, mock_api = _make_resource()
    mock_api.users.return_value.list.return_value.execute.side_effect = _http_error(404)
    with pytest.raises(HttpError) as exc_info:
        resource._list("users", customer="C123")
    assert type(exc_info.value) is HttpError


# ── callback ──────────────────────────────────────────────────────────────────


def test_callback_logs_response_and_appends_nothing_on_success():
    resource = GoogleDirectoryResource(customer_id="C123")
    resource._log = MagicMock()
    resource._exceptions = []
    resource.callback("1", {"kind": "admin#directory#user", "id": "u1"}, None)
    resource._log.info.assert_called_once()
    assert resource._exceptions == []


def test_callback_appends_exception_with_zero_based_index():
    resource = GoogleDirectoryResource(customer_id="C123")
    resource._log = MagicMock()
    resource._exceptions = []
    exc = Exception("insert failed")
    resource.callback("3", None, exc)
    assert resource._exceptions == [(2, exc)]  # int("3") - 1 = 2


def test_callback_preserves_earlier_exceptions_within_same_batch():
    resource = GoogleDirectoryResource(customer_id="C123")
    resource._log = MagicMock()
    first_exc = Exception("first")
    resource._exceptions = [(0, first_exc)]
    second_exc = Exception("second")
    resource.callback("2", None, second_exc)
    assert len(resource._exceptions) == 2
    assert resource._exceptions[0] == (0, first_exc)


# ── batch_insert_users ────────────────────────────────────────────────────────


def test_batch_insert_users_returns_empty_on_all_success():
    resource, mock_api = _make_resource()
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[({"primaryEmail": "a@b.com"}, None)]]
    )
    assert resource.batch_insert_users([{"primaryEmail": "a@b.com"}]) == []


def test_batch_insert_users_collects_exception_from_failed_request():
    resource, mock_api = _make_resource()
    err = _http_error(409, b"Entity already exists")
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[(None, err)]]
    )
    exceptions = resource.batch_insert_users([{"primaryEmail": "a@b.com"}])
    assert len(exceptions) == 1
    assert "a@b.com" in exceptions[0]


def test_batch_insert_users_collects_all_exceptions_from_multi_failure_batch():
    # Regression: old callback reset self._exceptions on every invocation, so
    # only the last exception per batch was ever collected.
    resource, mock_api = _make_resource()
    err1 = _http_error(409, b"Conflict")
    err2 = _http_error(409, b"Conflict")
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[(None, err1), (None, err2)]]
    )
    users = [{"primaryEmail": "a@b.com"}, {"primaryEmail": "b@b.com"}]
    exceptions = resource.batch_insert_users(users)
    assert len(exceptions) == 2


def test_batch_insert_users_sleeps_between_batches_not_after_last():
    resource, mock_api = _make_resource()
    # 11 users → 2 batches (10 + 1); sleep should fire exactly once
    users = [{"primaryEmail": f"u{i}@b.com"} for i in range(11)]
    batch1 = [({"primaryEmail": f"u{i}@b.com"}, None) for i in range(10)]
    batch2 = [({"primaryEmail": "u10@b.com"}, None)]
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [batch1, batch2]
    )
    with patch(
        "teamster.libraries.google.directory.resources.time.sleep"
    ) as mock_sleep:
        resource.batch_insert_users(users)
    mock_sleep.assert_called_once_with(1)


# ── batch_update_users ────────────────────────────────────────────────────────


def test_batch_update_users_returns_empty_on_all_success():
    resource, mock_api = _make_resource()
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[({"primaryEmail": "a@b.com"}, None)]]
    )
    assert resource.batch_update_users([{"primaryEmail": "a@b.com"}]) == []


def test_batch_update_users_collects_exception_from_failed_request():
    resource, mock_api = _make_resource()
    err = _http_error(400, b"Bad Request")
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[(None, err)]]
    )
    exceptions = resource.batch_update_users([{"primaryEmail": "a@b.com"}])
    assert len(exceptions) == 1


def test_batch_update_users_retries_409_conflict_and_succeeds():
    resource, mock_api = _make_resource()
    err = _http_error(409, b"Conflicting requests. Please try again")
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[(None, err)]]
    )
    mock_api.users.return_value.update.return_value.execute.return_value = {
        "primaryEmail": "a@b.com"
    }
    with patch("teamster.libraries.google.directory.resources.time.sleep"):
        exceptions = resource.batch_update_users([{"primaryEmail": "a@b.com"}])
    assert exceptions == []


def test_batch_update_users_collects_exception_when_409_retry_also_fails():
    resource, mock_api = _make_resource()
    err = _http_error(409, b"Conflicting requests. Please try again")
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[(None, err)]]
    )
    mock_api.users.return_value.update.return_value.execute.side_effect = _http_error(
        409, b"Conflicting requests. Please try again"
    )
    with patch("teamster.libraries.google.directory.resources.time.sleep"):
        exceptions = resource.batch_update_users([{"primaryEmail": "a@b.com"}])
    assert len(exceptions) == 1
    assert "a@b.com" in exceptions[0]


# ── batch_insert_members ──────────────────────────────────────────────────────


def test_batch_insert_members_returns_empty_on_all_success():
    resource, mock_api = _make_resource()
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[({"email": "a@b.com"}, None)]]
    )
    assert (
        resource.batch_insert_members([{"groupKey": "g@b.com", "email": "a@b.com"}])
        == []
    )


# ── batch_insert_role_assignments ─────────────────────────────────────────────


def test_batch_insert_role_assignments_returns_empty_on_all_success():
    resource, mock_api = _make_resource()
    mock_api.new_batch_http_request.side_effect = _make_batch_side_effect(
        [[({"roleAssignmentId": "ra1"}, None)]]
    )
    assert (
        resource.batch_insert_role_assignments(
            [{"assignedTo": "uid", "roleId": "rid", "scopeType": "CUSTOMER"}]
        )
        == []
    )


# ── list_roles / list_role_assignments default params ─────────────────────────


def test_list_roles_uses_max_results_100_and_items_key():
    resource, mock_api = _make_resource()
    mock_api.roles.return_value.list.return_value.execute.return_value = {
        "items": [{"roleId": "r1"}]
    }
    data = resource.list_roles()
    assert data == [{"roleId": "r1"}]
    _, call_kwargs = mock_api.roles.return_value.list.call_args
    assert call_kwargs["maxResults"] == 100


def test_list_role_assignments_uses_max_results_200_and_items_key():
    resource, mock_api = _make_resource()
    mock_api.roleAssignments.return_value.list.return_value.execute.return_value = {
        "items": [{"roleAssignmentId": "ra1"}]
    }
    data = resource.list_role_assignments()
    assert data == [{"roleAssignmentId": "ra1"}]
    _, call_kwargs = mock_api.roleAssignments.return_value.list.call_args
    assert call_kwargs["maxResults"] == 200


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
