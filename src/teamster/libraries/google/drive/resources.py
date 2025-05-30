from datetime import datetime

from dagster import ConfigurableResource, InitResourceContext
from dagster_shared import check
from google import auth
from googleapiclient import discovery
from pydantic import PrivateAttr


class GoogleDriveResource(ConfigurableResource):
    version: str = "v3"
    scopes: list[str] = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
    service_account_file_path: str | None = None

    _service: discovery.Resource = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)

        if self.service_account_file_path is not None:
            credentials, _ = auth.load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )
        else:
            credentials, _ = auth.default(scopes=self.scopes)

        self._service = discovery.build(
            serviceName="drive", version=self.version, credentials=credentials
        ).files()

    def files_list(
        self,
        corpora: str | None = None,
        drive_id: str | None = None,
        include_items_from_all_drives: bool | None = None,
        order_by: str | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
        q: str | None = None,
        spaces: str | None = None,
        supports_all_drives: bool | None = None,
        include_permissions_for_view: str | None = None,
        include_labels: str | None = None,
        fields: str | None = None,
    ) -> list[dict]:
        """https://developers.google.com/drive/api/reference/rest/v3/files/list

        Lists the user's files.

        This method accepts the q parameter, which is a search query combining one or more search terms. For more information, see the Search for files & folders guide.

        Args:
            corpora: Bodies of items (files/documents) to which the query applies.
                Supported bodies are 'user', 'domain', 'drive', and 'allDrives'. Prefer
                'user' or 'drive' to 'allDrives' for efficiency. By default, corpora is
                set to 'user'. However, this can change depending on the filter set
                through the 'q' parameter.
            driveId: ID of the shared drive to search.
            includeItemsFromAllDrives: Whether both My Drive and shared drive items
                should be included in results.
            orderBy: A comma-separated list of sort keys. Valid keys are:
                    - createdTime: When the file was created.
                    - folder: The folder ID. This field is sorted using alphabetical
                        ordering.
                    - modifiedByMeTime: The last time the file was modified by the user.
                    - modifiedTime: The last time the file was modified by anyone.
                    - name: The name of the file. This field is sorted using
                        alphabetical
                        ordering, so 1, 12, 2, 22.
                    - name_natural: The name of the file. This field is sorted using
                        natural sort ordering, so 1, 2, 12, 22.
                    - quotaBytesUsed: The number of storage quota bytes used by the
                        file.
                    - recency: The most recent timestamp from the file's date-time
                        fields.
                    - sharedWithMeTime: When the file was shared with the user, if
                        applicable.
                    - starred: Whether the user has starred the file.
                    - viewedByMeTime: The last time the file was viewed by the user.
                Each key sorts ascending by default, but can be reversed with the
                'desc' modifier. Example usage: ?orderBy=folder,modifiedTime desc,
                name.
            pageSize: The maximum number of files to return per page. Partial or empty
                result pages are possible even before the end of the files list has
                been reached.
            pageToken: The token for continuing a previous list request on the next
                page. This should be set to the value of 'nextPageToken' from the
                previous response.
            q: A query for filtering the file results. See the "Search for files &
                folders" guide for supported syntax.
            spaces: A comma-separated list of spaces to query within the corpora.
                Supported values are 'drive' and 'appDataFolder'.
            supportsAllDrives: Whether the requesting application supports both My
                Drives and shared drives.
            includePermissionsForView: Specifies which additional view's permissions to
                include in the response. Only 'published' is supported.
            includeLabels: A comma-separated list of IDs of labels to include in the
                labelInfo part of the response.
        """
        all_files = []

        # trunk-ignore(pyright/reportAttributeAccessIssue)
        request = self._service.list(
            corpora=corpora,
            driveId=drive_id,
            includeItemsFromAllDrives=include_items_from_all_drives,
            orderBy=order_by,
            pageSize=page_size,
            pageToken=page_token,
            q=q,
            spaces=spaces,
            supportsAllDrives=supports_all_drives,
            includePermissionsForView=include_permissions_for_view,
            includeLabels=include_labels,
            fields=f"files({fields})",
        )

        while request is not None:
            response = request.execute()

            all_files.extend(response["files"])

            # trunk-ignore(pyright/reportAttributeAccessIssue)
            request = self._service.list_next(request, response)

        return all_files

    def files_list_recursive(
        self,
        corpora: str,
        drive_id: str,
        include_items_from_all_drives: bool,
        supports_all_drives: bool,
        fields: str,
        folder_id: str,
        file_path: str = "",
        exclude: list[str] | None = None,
        files: list | None = None,
    ) -> list:
        if exclude is None:
            exclude = []

        if files is None:
            files = []

        if file_path in exclude:
            return files

        self._log.info(f"Listing of all files under {file_path}")
        files_list = self.files_list(
            corpora=corpora,
            drive_id=drive_id,
            include_items_from_all_drives=include_items_from_all_drives,
            q=f"'{folder_id}' in parents and trashed = false",
            supports_all_drives=supports_all_drives,
            fields=fields,
        )

        for file in files_list:
            file_subpath = f"{file_path}/{file['name']}"

            if file["mimeType"] == "application/vnd.google-apps.folder":
                self.files_list_recursive(
                    corpora=corpora,
                    drive_id=drive_id,
                    include_items_from_all_drives=include_items_from_all_drives,
                    supports_all_drives=supports_all_drives,
                    folder_id=file["id"],
                    file_path=file_subpath,
                    exclude=exclude,
                    files=files,
                    fields=fields,
                )
            else:
                file["path"] = f"{file_path}/{file['name']}"
                file["size"] = int(file["size"])
                file["modified_timestamp"] = datetime.strptime(
                    file["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
                ).timestamp()

                files.append(file)

        return files
