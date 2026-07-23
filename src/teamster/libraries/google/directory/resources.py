import time
from collections.abc import Callable

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster._utils.backoff import backoff, exponential_delay_generator
from dagster_shared import check
from google.auth import default, load_credentials_from_file
from google.auth.compute_engine import Credentials
from google.auth.iam import Signer
from google.auth.transport import requests
from google.oauth2 import service_account
from googleapiclient import discovery, errors
from pydantic import PrivateAttr

from teamster.core.utils.functions import chunk

_TRANSIENT_HTTP_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Total attempts per batch (1 initial + retries) for sub-requests that fail with
# a transient code. Matches dagster.backoff's default retry budget (1 + 4).
_MAX_BATCH_ATTEMPTS: int = 5


class _TransientHttpError(errors.HttpError):
    """``HttpError`` subclass raised only for retryable (5xx, 429) responses.

    Used as the ``retry_on`` target for :func:`backoff` so that client errors
    (4xx) propagate immediately instead of being retried.
    """


def _retryable_execute(request) -> Callable[[], dict]:
    """Return a zero-arg callable that executes ``request`` and re-raises transient errors.

    Calls ``request.execute()``. If an ``HttpError`` with a status code in
    ``_TRANSIENT_HTTP_CODES`` (5xx, 429) is raised it is re-raised as
    ``_TransientHttpError`` so that :func:`backoff` will retry it. All other
    ``HttpError`` responses (4xx) are re-raised immediately.

    Args:
        request: Any object with an ``execute()`` method (Google API request or
            ``BatchHttpRequest``).

    Returns:
        A zero-arg callable suitable for passing to :func:`backoff`.
    """

    def execute() -> dict:
        try:
            return request.execute()
        except errors.HttpError as e:
            if e.resp.status in _TRANSIENT_HTTP_CODES:
                raise _TransientHttpError(e.resp, e.content) from e
            raise

    return execute


class GoogleDirectoryResource(ConfigurableResource):
    """Google Admin SDK Directory API resource.

    Authenticates via service account with domain-wide delegation or Workload
    Identity on GCE. Wraps the Admin SDK Directory API v1 with paginated list
    helpers and batch mutation methods.

    Attributes:
        customer_id: Google Workspace customer ID (use ``"my_customer"`` for
            the primary domain).
        version: Directory API version. Defaults to ``"v1"``.
        max_results: Default page size for list operations. Defaults to 500.
        scopes: OAuth 2.0 scopes requested during authentication.
        service_account_file_path: Path to a service account JSON key file.
            If ``None``, Workload Identity (GCE/Cloud Run) is used instead.
        delegated_account: Email of the Google Workspace admin to impersonate
            via domain-wide delegation.
    """

    customer_id: str
    version: str = "v1"
    max_results: int = 500
    scopes: list[str] = [
        "https://www.googleapis.com/auth/admin.directory.user",
        "https://www.googleapis.com/auth/admin.directory.group",
        "https://www.googleapis.com/auth/admin.directory.rolemanagement",
        "https://www.googleapis.com/auth/admin.directory.orgunit",
    ]
    service_account_file_path: str | None = None
    delegated_account: str | None = None

    _resource: discovery.Resource = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()
    _exceptions: list[tuple] = PrivateAttr(default_factory=list)

    def setup_for_execution(self, context: InitResourceContext) -> None:
        """Initialize the Directory API client before asset execution.

        Selects one of two credential paths based on ``service_account_file_path``:

        - **Service account key file** (local dev): loads credentials from the
          JSON key file and impersonates ``delegated_account``.
        - **Workload Identity** (GCE/Cloud Run): uses the instance's default
          service account with IAM-based signing to obtain impersonated
          credentials without a key file on disk.

        Args:
            context: Dagster resource init context; provides the logger.
        """
        self._log = check.not_none(value=context.log)

        if self.service_account_file_path is not None:
            credentials, _ = load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )

            credentials = check.inst(
                credentials, service_account.Credentials
            ).with_subject(self.delegated_account)
        else:
            # https://stackoverflow.com/a/57092533
            # https://github.com/GoogleCloudPlatform/professional-services/tree/main/examples/gce-to-adminsdk
            request = requests.Request()
            source_credentials, _ = default()

            source_credentials = check.inst(obj=source_credentials, ttype=Credentials)

            # Refresh the default credentials. This ensures that the information about
            # this account, notably the email, is populated.
            source_credentials.refresh(request)

            # Create OAuth 2.0 Service Account credentials using the IAM-based signer
            # and the bootstrap credential's service account email.
            credentials = service_account.Credentials(
                signer=Signer(
                    request=request,
                    credentials=source_credentials,
                    service_account_email=source_credentials.service_account_email,
                ),
                service_account_email=source_credentials.service_account_email,
                # trunk-ignore(bandit/B106)
                token_uri="https://accounts.google.com/o/oauth2/token",
                scopes=self.scopes,
                subject=self.delegated_account,
            )

        self._resource = discovery.build(
            serviceName="admin",
            version=f"directory_{self.version}",
            credentials=credentials,
        )

    def _list(self, api_name: str, **kwargs) -> list[dict]:
        """Paginate through all pages of a Directory API list endpoint.

        Retries each page request on transient ``HttpError`` (e.g. 503) using
        fixed-delay backoff before raising.

        Args:
            api_name: Resource name on the Directory API client (e.g.
                ``"users"``, ``"groups"``).
            **kwargs: Forwarded to the API's ``list()`` call. ``response_data_key``
                (default: ``api_name``) and ``max_results`` (default:
                ``self.max_results``) are consumed locally.

        Returns:
            Flat list of all records across all pages.

        Raises:
            HttpError: If all retry attempts are exhausted.
        """
        data = []
        next_page_token = None

        response_data_key = kwargs.pop("response_data_key", api_name)
        max_results = kwargs.pop("max_results", self.max_results)

        while True:
            response = backoff(
                fn=_retryable_execute(
                    getattr(self._resource, api_name)().list(
                        pageToken=next_page_token, maxResults=max_results, **kwargs
                    )
                ),
                retry_on=(_TransientHttpError,),
            )

            next_page_token = response.get("nextPageToken")
            data.extend(response.get(response_data_key, []))

            self._log.debug(f"Retrieved {len(data)} records")

            if next_page_token is None:
                break

        return data

    def list_orgunits(
        self,
        org_unit_path: str | None = None,
        org_unit_type: str | None = None,
        customer_id: str | None = None,
        **kwargs,
    ) -> dict:
        """Retrieves a list of all organizational units for an account.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/orgunits/list)

        Args:
            org_unit_path: Full path or unique ID; returns children of that unit.
            org_unit_type: ``"all"`` or ``"children"`` (immediate only).
            customer_id: Defaults to ``self.customer_id``.

        Returns:
            OrgUnits response dict.

        Raises:
            HttpError: If the API request fails.
        """
        if customer_id is None:
            customer_id = self.customer_id

        return (
            # trunk-ignore(pyright/reportAttributeAccessIssue)
            self._resource.orgunits()
            .list(
                customerId=customer_id,
                orgUnitPath=org_unit_path,
                type=org_unit_type,
                **kwargs,
            )
            .execute()
        )

    def get_orgunit(
        self, org_unit_path: str, customer_id: str | None = None, **kwargs
    ) -> dict:
        """Retrieves an organizational unit.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/orgunits/get)

        Args:
            org_unit_path: Full path or unique ID of the org unit.
            customer_id: Defaults to ``self.customer_id``.

        Returns:
            OrganizationalUnit resource dict.

        Raises:
            HttpError: If the API request fails.
        """
        if customer_id is None:
            customer_id = self.customer_id

        return (
            # trunk-ignore(pyright/reportAttributeAccessIssue)
            self._resource.orgunits()
            .get(customerId=customer_id, orgUnitPath=org_unit_path, **kwargs)
            .execute()
        )

    def list_users(self, **kwargs) -> list[dict]:
        """Retrieves a paginated list of either deleted users or all users in a domain.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/list)

        Args:
            **kwargs: Forwarded to ``_list``. ``customer`` defaults to
                ``self.customer_id``.

        Returns:
            List of user resource dicts.

        Raises:
            HttpError: If all retry attempts are exhausted.
        """
        customer = kwargs.pop("customer", self.customer_id)
        return self._list(api_name="users", customer=customer, **kwargs)

    def get_user(self, user_key: str, **kwargs) -> dict:
        """Retrieves a user.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/get)

        Args:
            user_key: Primary email, alias, or unique user ID.

        Returns:
            User resource dict.

        Raises:
            HttpError: If the API request fails.
        """
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.users().get(userKey=user_key, **kwargs).execute()

    def list_groups(self, **kwargs) -> list[dict]:
        """Retrieves all groups of a domain or of a user given a userKey.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups/list)

        Args:
            **kwargs: Forwarded to ``_list``. ``customer`` defaults to
                ``self.customer_id``.

        Returns:
            List of group resource dicts.

        Raises:
            HttpError: If all retry attempts are exhausted.
        """
        customer = kwargs.pop("customer", self.customer_id)
        return self._list(api_name="groups", customer=customer, **kwargs)

    def list_members(self, group_key: str, **kwargs) -> list[dict]:
        """Retrieves a paginated list of all members in a group.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/members/list)

        Args:
            group_key: Group email, alias, or unique ID.

        Returns:
            List of member resource dicts.

        Raises:
            HttpError: If all retry attempts are exhausted.
        """
        return self._list(api_name="members", groupKey=group_key, **kwargs)

    def list_roles(self, **kwargs) -> list[dict]:
        """Retrieves a paginated list of all the roles in a domain.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/roles/list)

        Args:
            **kwargs: Forwarded to ``_list``. ``customer`` defaults to
                ``self.customer_id``. Page size defaults to 100 (API maximum).

        Returns:
            List of role resource dicts.

        Raises:
            HttpError: If all retry attempts are exhausted.
        """
        customer = kwargs.pop("customer", self.customer_id)
        max_results = kwargs.pop("max_results", 100)
        return self._list(
            api_name="roles",
            customer=customer,
            max_results=max_results,
            response_data_key="items",
            **kwargs,
        )

    def list_role_assignments(self, **kwargs) -> list[dict]:
        """Retrieves a paginated list of all role assignments.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/roleAssignments/list)

        Args:
            **kwargs: Forwarded to ``_list``. ``customer`` defaults to
                ``self.customer_id``. Page size defaults to 200.

        Returns:
            List of role assignment resource dicts.

        Raises:
            HttpError: If all retry attempts are exhausted.
        """
        customer = kwargs.pop("customer", self.customer_id)
        max_results = kwargs.pop("max_results", 200)
        return self._list(
            api_name="roleAssignments",
            customer=customer,
            max_results=max_results,
            response_data_key="items",
            **kwargs,
        )

    def insert_user(self, body: dict) -> dict:
        """Creates a user.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/insert)

        Args:
            body: User resource dict.

        Returns:
            Created user resource dict.

        Raises:
            HttpError: If the API request fails.
        """
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.users().insert(body=body).execute()

    def update_user(self, user_key: str, body: dict) -> dict:
        """Updates a user.

        [API reference](https://developers.google.com/admin-sdk/directory/reference/rest/v1/users/update)

        Args:
            user_key: Primary email, alias, or unique user ID.
            body: User resource dict with the fields to update.

        Returns:
            Updated user resource dict.

        Raises:
            HttpError: If the API request fails.
        """
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.users().update(userKey=user_key, body=body).execute()

    def callback(
        self, id: str, response: dict | None, exception: Exception | None
    ) -> None:
        """Callback for batch HTTP requests.

        Called once per request by the batch executor. Logs the response or
        exception; exceptions are appended to ``self._exceptions`` for later
        inspection by the caller. The list must be reset by the caller before
        each batch (not here — resetting in the callback would wipe earlier
        results within the same batch).

        Args:
            id: 1-based string index of the request within the batch.
            response: Response body dict; ``None`` when ``exception`` is set.
            exception: Raised exception; ``None`` on success.
        """
        if exception is not None:
            # WARNING, not exception: batch sub-request failures are retried by
            # _execute_batch_with_retry, so logging a traceback at ERROR here
            # would file false-positive GCP Error Reporting groups for transient
            # failures the retry layer recovers from.
            self._log.warning(msg=(id, exception))
            self._exceptions.append((int(id) - 1, exception))
        else:
            self._log.info(
                msg=" ".join([f"{k}={v}" for k, v in check.not_none(response).items()])
            )

    def _execute_batch_with_retry(
        self,
        items: list[dict],
        request_factory: Callable[[dict], object],
    ) -> list[tuple[dict, Exception]]:
        """Execute one batch, retrying only sub-requests that fail transiently.

        A ``BatchHttpRequest`` never raises for an individual sub-request
        failure — the result is delivered to :meth:`callback` and ``execute()``
        returns normally — so wrapping ``execute()`` in :func:`backoff` retries
        only a failure of the whole batch envelope, not a per-sub-request 5xx.
        This helper adds sub-request-level retry: after each batch, sub-requests
        that failed with a transient code (429, 5xx) are re-submitted in a
        follow-up batch with exponential backoff, up to ``_MAX_BATCH_ATTEMPTS``
        total attempts. Already-succeeded sub-requests are not re-sent.

        Args:
            items: Resource dicts for the batch.
            request_factory: Builds the API request object for a single item.

        Returns:
            ``(item, exception)`` for each sub-request that ultimately failed —
            either non-transient, or transient after exhausting retries.
        """
        pending = list(items)
        failures: list[tuple[dict, Exception]] = []
        delays = exponential_delay_generator()

        for attempt in range(1, _MAX_BATCH_ATTEMPTS + 1):
            self._exceptions = []

            # trunk-ignore(pyright/reportAttributeAccessIssue)
            batch_request = self._resource.new_batch_http_request(
                callback=self.callback
            )

            for item in pending:
                batch_request.add(request_factory(item))

            # Retries a transient failure of the whole batch envelope; individual
            # sub-request failures come back through self._exceptions below.
            backoff(
                fn=_retryable_execute(batch_request), retry_on=(_TransientHttpError,)
            )

            if not self._exceptions:
                return failures

            retryable = []
            for ix, exc in self._exceptions:
                item = pending[ix]

                if (
                    attempt < _MAX_BATCH_ATTEMPTS
                    and isinstance(exc, errors.HttpError)
                    and exc.resp.status in _TRANSIENT_HTTP_CODES
                ):
                    retryable.append(item)
                else:
                    failures.append((item, exc))

            pending = retryable
            if not pending:
                break

            time.sleep(next(delays))

        return failures

    def batch_insert_users(self, users: list[dict]) -> list[str]:
        """Create multiple users in batches of 10.

        Respects the 10-users-per-domain-per-second API limit. Each batch — and
        each individual sub-request within it — is retried on transient errors
        (5xx, 429) with backoff.

        Args:
            users: User resource dicts to create.

        Returns:
            Error strings for any failed requests.
        """
        exceptions = []

        # You cannot create more than 10 users per domain per second using the
        # Directory API
        # developers.google.com/admin-sdk/directory/v1/limits#api-limits-and-quotas
        batches = list(chunk(obj=users, size=10))

        for i, batch in enumerate(batches):
            self._log.info(msg=f"Processing batch {i + 1}")

            failures = self._execute_batch_with_retry(
                items=batch,
                # trunk-ignore(pyright/reportAttributeAccessIssue)
                request_factory=lambda user: self._resource.users().insert(body=user),
            )

            exceptions.extend(f"{item} {e}" for item, e in failures)

            if i < len(batches) - 1:
                time.sleep(1)

        return exceptions

    def _retry_update_user(self, user: dict) -> None:
        """Retry a single user update after a 409 conflict response."""
        self._log.info(msg=f"Retrying 409 conflict for {user['primaryEmail']}")

        time.sleep(1)

        # backoff handles transient 5xx/429 within this attempt; a second 409
        # is deliberately not retried — it propagates as HttpError to the caller.
        backoff(
            fn=_retryable_execute(
                # trunk-ignore(pyright/reportAttributeAccessIssue)
                self._resource.users().update(userKey=user["primaryEmail"], body=user)
            ),
            retry_on=(_TransientHttpError,),
        )

    def batch_update_users(self, users: list[dict]) -> list[str]:
        """Update multiple users in batches of 40.

        Args:
            users: User resource dicts to update; each must include
                ``primaryEmail``.

        Returns:
            Error strings for any failed requests.
        """
        exceptions = []

        # Queries per minute per user == 2400 (40/sec)
        batches = list(chunk(obj=users, size=40))

        for i, batch in enumerate(batches):
            self._log.info(msg=f"Processing batch {i + 1}")

            failures = self._execute_batch_with_retry(
                items=batch,
                request_factory=lambda user: (
                    # trunk-ignore(pyright/reportAttributeAccessIssue)
                    self._resource.users().update(
                        userKey=user["primaryEmail"], body=user
                    )
                ),
            )

            for user, e in failures:
                if isinstance(e, errors.HttpError) and e.resp.status == 409:
                    try:
                        self._retry_update_user(user)
                    except errors.HttpError as retry_e:
                        exceptions.append(f"{user} {retry_e}")
                else:
                    exceptions.append(f"{user} {e}")

            if i < len(batches) - 1:
                time.sleep(1)

        return exceptions

    def batch_insert_members(self, members: list[dict]) -> list[str]:
        """Add multiple members to groups in batches of 40.

        Each batch — and each individual sub-request within it — is retried on
        transient errors (5xx, 429) with backoff.

        Args:
            members: Member resource dicts; each must include ``groupKey`` and
                ``email``.

        Returns:
            Error strings for any failed requests.
        """
        exceptions = []

        # Queries per minute per user == 2400 (40/sec)
        batches = list(chunk(obj=members, size=40))

        for i, batch in enumerate(batches):
            self._log.info(msg=f"Processing batch {i + 1}")

            failures = self._execute_batch_with_retry(
                items=batch,
                request_factory=lambda member: (
                    # trunk-ignore(pyright/reportAttributeAccessIssue)
                    self._resource.members().insert(
                        groupKey=member["groupKey"], body=member
                    )
                ),
            )

            exceptions.extend(f"{item} {e}" for item, e in failures)

            if i < len(batches) - 1:
                time.sleep(1)

        return exceptions

    def batch_insert_role_assignments(
        self, role_assignments: list[dict], customer: str | None = None
    ) -> list[str]:
        """Create multiple role assignments in batches of 10.

        Each batch — and each individual sub-request within it — is retried on
        transient errors (5xx, 429) with exponential backoff to handle quota
        exhaustion gracefully.

        Args:
            role_assignments: Role assignment resource dicts.
            customer: Defaults to ``self.customer_id``.

        Returns:
            Error strings for any failed requests.
        """
        exceptions = []

        batches = list(chunk(obj=role_assignments, size=10))

        for i, batch in enumerate(batches):
            self._log.info(msg=f"Processing batch {i + 1}")

            failures = self._execute_batch_with_retry(
                items=batch,
                request_factory=lambda role_assignment: (
                    # trunk-ignore(pyright/reportAttributeAccessIssue)
                    self._resource.roleAssignments().insert(
                        customer=(customer or self.customer_id),
                        body=role_assignment,
                    )
                ),
            )

            exceptions.extend(f"{item} {e}" for item, e in failures)

            if i < len(batches) - 1:
                time.sleep(1)

        return exceptions
