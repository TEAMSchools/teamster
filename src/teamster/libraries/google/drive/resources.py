import google.auth
from dagster import ConfigurableResource, InitResourceContext
from googleapiclient import discovery
from pydantic import PrivateAttr


class GoogleDriveResource(ConfigurableResource):
    service_account_file_path: str | None = None
    version: str = "v3"
    scopes: list = ["https://www.googleapis.com/auth/drive.metadata.readonly"]

    _service: discovery.Resource = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        if self.service_account_file_path is not None:
            credentials, project_id = google.auth.load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )
        else:
            credentials, project_id = google.auth.default(scopes=self.scopes)

        self._service = discovery.build(
            serviceName="drive", version=self.version, credentials=credentials
        ).files()

    def _list(self, **kwargs):
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        return self._service.list(**kwargs).execute()

    def list_files(self, **kwargs):
        """Lists the user's files.
        https://developers.google.com/drive/api/reference/rest/v3/files/list

        Args:
            corpora (str | None): Bodies of items (files/documents) to which the query
                applies. Supported bodies are 'user', 'domain', 'drive', and
                'allDrives'. Prefer 'user' or 'drive' to 'allDrives' for efficiency. By
                default, corpora is set to 'user'. However, this can change depending
                on the filter set through the 'q' parameter.
            driveId (str | None): ID of the shared drive to search.
            includeItemsFromAllDrives (bool | None): Whether both My Drive and shared
                drive items should be included in results.
            orderBy (str | None): A comma-separated list of sort keys. Valid keys are
                'createdTime', 'folder', 'modifiedByMeTime', 'modifiedTime', 'name',
                'name_natural', 'quotaBytesUsed', 'recency', 'sharedWithMeTime',
                'starred', and 'viewedByMeTime'. Each key sorts ascending by default,
                but can be reversed with the 'desc' modifier. Example usage: ?
                orderBy=folder,modifiedTime desc,name.
            pageSize (int | None): The maximum number of files to return per page.
                Partial or empty result pages are possible even before the end of the
                files list has been reached.
            pageToken (str | None): The token for continuing a previous list request on
                the next page. This should be set to the value of 'nextPageToken' from
                the previous response.
            q (str | None): A query for filtering the file results. See the "Search for
                files & folders" guide for supported syntax.
            spaces (str | None): A comma-separated list of spaces to query within the
                corpora. Supported values are 'drive' and 'appDataFolder'.
            supportsAllDrives (bool | None): Whether the requesting application
                supports both My Drives and shared drives.
            includePermissionsForView (str | None): Specifies which additional view's
                permissions to include in the response. Only 'published' is supported.
            includeLabels (str | None): A comma-separated list of IDs of labels to
                include in the labelInfo part of the response.
        """

        next_page_token = None
        files = []

        while True:
            response = self._list(pageToken=next_page_token, **kwargs)

            next_page_token = response.get("nextPageToken")
            files.extend(response["files"])

            if next_page_token is None:
                break

        return files
