import time

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from dagster._utils.backoff import backoff
from google.auth import default, impersonated_credentials, load_credentials_from_file
from google.oauth2 import service_account
from googleapiclient import discovery, errors
from pydantic import PrivateAttr


class GoogleDirectoryResource(ConfigurableResource):
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
    _exceptions: list[tuple] = PrivateAttr(default=[])

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)

        if self.service_account_file_path is not None:
            credentials, project_id = load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )

            credentials = _check.inst(
                credentials, service_account.Credentials
            ).with_subject(self.delegated_account)
        else:
            # https://cloud.google.com/iam/docs/create-short-lived-credentials-direct#user-credentials
            source_credentials, project_id = default()

            credentials = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=self.delegated_account,
                target_scopes=self.scopes,
            )

        self._resource = discovery.build(
            serviceName="admin",
            version=f"directory_{self.version}",
            credentials=credentials,
        )

    def _list(self, api_name, **kwargs):
        data = []
        next_page_token = None

        response_data_key = kwargs.pop("response_data_key", api_name)
        max_results = kwargs.pop("max_results", self.max_results)

        while True:
            response = (
                getattr(self._resource, api_name)()
                .list(pageToken=next_page_token, maxResults=max_results, **kwargs)
                .execute()
            )

            next_page_token = response.get("nextPageToken")
            data.extend(response[response_data_key])

            self._log.debug(f"Retrieved {len(data)} records")

            if next_page_token is None:
                break

        return data

    def list_orgunits(
        self, org_unit_path=None, org_unit_type=None, customer_id=None, **kwargs
    ):
        return (
            # trunk-ignore(pyright/reportAttributeAccessIssue)
            self._resource.orgunits()
            .list(
                customerId=(customer_id or self.customer_id),
                orgUnitPath=org_unit_path,
                type=org_unit_type,
                **kwargs,
            )
            .execute()
        )

    def get_orgunit(self, org_unit_path, customer_id=None, **kwargs):
        return (
            # trunk-ignore(pyright/reportAttributeAccessIssue)
            self._resource.orgunits()
            .get(
                customerId=(customer_id or self.customer_id),
                orgUnitPath=org_unit_path,
                **kwargs,
            )
            .execute()
        )

    def list_users(self, **kwargs):
        return self._list(
            api_name="users",
            customer=kwargs.get("customer", self.customer_id),
            **kwargs,
        )

    def get_user(self, user_key, **kwargs):
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.users().get(userKey=user_key, **kwargs).execute()

    def list_groups(self, **kwargs):
        return self._list(
            api_name="groups",
            customer=kwargs.get("customer", self.customer_id),
            **kwargs,
        )

    def list_members(self, group_key, **kwargs):
        return self._list(api_name="members", groupKey=group_key, **kwargs)

    def list_roles(self, **kwargs):
        return self._list(
            api_name="roles",
            customer=kwargs.get("customer", self.customer_id),
            max_results=kwargs.get("max_results", 100),
            response_data_key="items",
            **kwargs,
        )

    def list_role_assignments(self, **kwargs):
        return self._list(
            api_name="roleAssignments",
            customer=kwargs.get("customer", self.customer_id),
            max_results=kwargs.get("max_results", 200),
            response_data_key="items",
            **kwargs,
        )

    def insert_user(self, body):
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.users().insert(body=body).execute()

    def update_user(self, user_key, body):
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._resource.users().update(userKey=user_key, body=body).execute()

    @staticmethod
    def _batch_list(list, size):
        """via https://stackoverflow.com/a/312464"""
        for i in range(0, len(list), size):
            yield list[i : i + size]

    @staticmethod
    def backoff_delay_generator():
        i = 1
        while True:
            yield i
            i = i * 2

    def batch_insert_users(self, users):
        def callback(id: str, response: dict, exception: Exception):
            if exception is not None:
                self._log.exception(msg=(id, exception))
                self._exceptions.append((int(id) - 1, exception))
            else:
                self._log.info(
                    msg="CREATED " + " ".join([f"{k}={v}" for k, v in response.items()])
                )

        exceptions = []

        # You cannot create more than 10 users per domain per second using the
        # Directory API
        # developers.google.com/admin-sdk/directory/v1/limits#api-limits-and-quotas
        batches = self._batch_list(list=users, size=10)

        for i, batch in enumerate(batches):
            self._log.info(msg=f"Processing batch {i + 1}")

            # trunk-ignore(pyright/reportAttributeAccessIssue)
            batch_request = self._resource.new_batch_http_request(callback=callback)

            for user in batch:
                # trunk-ignore(pyright/reportAttributeAccessIssue)
                batch_request.add(self._resource.users().insert(body=user))

            backoff(fn=batch_request.execute, retry_on=(errors.HttpError,))

            exceptions.extend([f"{batch[ix]} {e}" for ix, e in self._exceptions])

            time.sleep(1)

        return exceptions

    def batch_update_users(self, users):
        def callback(id: str, response: dict, exception: Exception):
            if exception is not None:
                self._log.exception(msg=(id, exception))
                self._exceptions.append((int(id) - 1, exception))
            else:
                self._log.info(
                    msg="UPDATED " + " ".join([f"{k}={v}" for k, v in response.items()])
                )

        exceptions = []

        # Queries per minute per user == 2400 (40/sec)
        batches = self._batch_list(list=users, size=40)

        for i, batch in enumerate(batches):
            self._log.info(msg=f"Processing batch {i + 1}")

            # trunk-ignore(pyright/reportAttributeAccessIssue)
            batch_request = self._resource.new_batch_http_request(callback=callback)

            for user in batch:
                batch_request.add(
                    # trunk-ignore(pyright/reportAttributeAccessIssue)
                    self._resource.users().update(
                        userKey=user["primaryEmail"], body=user
                    )
                )

            backoff(fn=batch_request.execute, retry_on=(errors.HttpError,))

            exceptions.extend([f"{batch[ix]} {e}" for ix, e in self._exceptions])

            time.sleep(1)

        return exceptions

    def batch_insert_members(self, members):
        def callback(id: str, response: dict, exception: Exception):
            if exception is not None:
                self._log.exception(msg=(id, exception))
                self._exceptions.append((int(id) - 1, exception))
            else:
                self._log.info(
                    msg="ADDING " + " ".join([f"{k}={v}" for k, v in response.items()])
                )

        exceptions = []

        # Queries per minute per user == 2400 (40/sec)
        batches = self._batch_list(list=members, size=40)

        for i, batch in enumerate(batches):
            self._log.info(msg=f"Processing batch {i + 1}")

            # trunk-ignore(pyright/reportAttributeAccessIssue)
            batch_request = self._resource.new_batch_http_request(callback=callback)

            for member in batch:
                batch_request.add(
                    # trunk-ignore(pyright/reportAttributeAccessIssue)
                    self._resource.members().insert(
                        groupKey=member["groupKey"], body=member
                    )
                )

            backoff(fn=batch_request.execute, retry_on=(errors.HttpError,))

            exceptions.extend([f"{batch[ix]} {e}" for ix, e in self._exceptions])

            time.sleep(1)

        return exceptions

    def batch_insert_role_assignments(self, role_assignments, customer=None):
        def callback(id: str, response: dict, exception: Exception):
            if exception is not None:
                self._log.exception(msg=(id, exception))
                self._exceptions.append((int(id) - 1, exception))
            else:
                self._log.info(msg=" ".join([f"{k}={v}" for k, v in response.items()]))

        exceptions = []

        batches = self._batch_list(list=role_assignments, size=10)

        for i, batch in enumerate(batches):
            self._log.info(msg=f"Processing batch {i + 1}")

            # trunk-ignore(pyright/reportAttributeAccessIssue)
            batch_request = self._resource.new_batch_http_request(callback=callback)

            for role_assignment in batch:
                batch_request.add(
                    # trunk-ignore(pyright/reportAttributeAccessIssue)
                    self._resource.roleAssignments().insert(
                        customer=(customer or self.customer_id),
                        body=role_assignment,
                    )
                )

            backoff(
                fn=batch_request.execute,
                retry_on=(errors.HttpError,),
                delay_generator=self.backoff_delay_generator(),
            )

            exceptions.extend([f"{batch[ix]} {e}" for ix, e in self._exceptions])

            time.sleep(1)

        return exceptions
