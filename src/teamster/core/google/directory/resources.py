import google.auth
from dagster import ConfigurableResource, InitResourceContext
from googleapiclient import discovery
from pydantic import PrivateAttr


class GoogleDirectoryResource(ConfigurableResource):
    customer_id: str
    service_account_file_path: str = None
    delegated_account: str = None
    version: str = "v1"
    scopes: list = [
        "https://www.googleapis.com/auth/admin.directory.user",
        "https://www.googleapis.com/auth/admin.directory.group",
        "https://www.googleapis.com/auth/admin.directory.rolemanagement",
    ]
    max_results: int = 500

    _service: discovery.Resource = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        if self.service_account_file_path is not None:
            credentials, project_id = google.auth.load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )

            credentials = credentials.with_subject(self.delegated_account)
        else:
            credentials, project_id = google.auth.default(scopes=self.scopes)

        self._service = discovery.build(
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
                getattr(self._service, api_name)()
                .list(pageToken=next_page_token, maxResults=max_results, **kwargs)
                .execute()
            )

            next_page_token = response.get("nextPageToken")
            data.extend(response[response_data_key])

            self.get_resource_context().log.debug(f"Retrieved {len(data)} records")

            if next_page_token is None:
                break

        return data

    def list_users(self, **kwargs):
        return self._list(
            "users", customer=kwargs.get("customer", self.customer_id), **kwargs
        )

    def get_user(self, user_key, **kwargs):
        return self._service.users().get(userKey=user_key, **kwargs).execute()

    def list_groups(self, **kwargs):
        return self._list(
            "groups", customer=kwargs.get("customer", self.customer_id), **kwargs
        )

    def list_members(self, group_key, **kwargs):
        return self._list("members", groupKey=group_key, **kwargs)

    def list_roles(self, **kwargs):
        return self._list(
            "roles",
            customer=kwargs.get("customer", self.customer_id),
            max_results=kwargs.get("max_results", 100),
            response_data_key="items",
            **kwargs,
        )

    def list_role_assignments(self, **kwargs):
        return self._list(
            "roleAssignments",
            customer=kwargs.get("customer", self.customer_id),
            max_results=kwargs.get("max_results", 200),
            response_data_key="items",
            **kwargs,
        )

    @staticmethod
    def _batch_list(list, size):
        """via https://stackoverflow.com/a/312464"""
        for i in range(0, len(list), size):
            yield list[i : i + size]

    def batch_update_users(self, users):
        def callback(request_id, response, exception):
            context = self.get_resource_context()

            if exception is not None:
                context.log.error(exception)
            else:
                context.log.info(
                    msg=(
                        f"UPDATED {response['primaryEmail']}: "
                        f"{response['name'].get('givenName')} "
                        f"{response['name'].get('familyName')} "
                        f"OU={response['orgUnitPath']} "
                        f"suspended={response['suspended']}"
                    )
                )

        batch_request = self._service.new_batch_http_request(callback=callback)

        for batch in self._batch_list(list=users, size=1000):
            for user in batch:
                batch_request.add(
                    self._service.users().update(
                        userKey=user["primaryEmail"], body=user
                    )
                )

            batch_request.execute()

    def batch_insert_users(self, users):
        def callback(request_id, response, exception):
            context = self.get_resource_context()

            if exception is not None:
                context.log.error(exception)
            else:
                context.log.info(
                    msg=(
                        f"CREATED {response['primaryEmail']}: "
                        f"{response['name'].get('givenName')} "
                        f"{response['name'].get('familyName')} "
                        f"OU={response['orgUnitPath']} "
                        f"changepassword={response['changePasswordAtNextLogin']}"
                    )
                )

        batch_request = self._service.new_batch_http_request(callback=callback)

        for batch in self._batch_list(list=users, size=1000):
            for user in batch:
                batch_request.add(self._service.users().insert(body=user))

            batch_request.execute()

    def batch_insert_members(self, members):
        context = self.get_resource_context()

        def callback(request_id, response, exception):
            context = self.get_resource_context()

            if exception is not None:
                context.log.error(exception)
            else:
                context.log.info(f"ADDED {response['email']}")

        batch_request = self._service.new_batch_http_request(callback=callback)

        for batch in self._batch_list(list=members, size=1000):
            for member in batch:
                context.log.info(f"ADDING {member['email']} to {member['groupKey']}")
                batch_request.add(
                    self._service.members().insert(
                        groupKey=member["groupKey"], body=member
                    )
                )

            batch_request.execute()
