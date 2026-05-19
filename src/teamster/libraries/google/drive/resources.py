from datetime import datetime
from logging import Logger

from dagster import ConfigurableResource, InitResourceContext
from dagster_shared import check
from google import auth
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from pydantic import PrivateAttr


class GoogleDriveResource(ConfigurableResource):
    version: str = "v3"
    scopes: list[str] = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
    service_account_file_path: str | None = None

    _drive: discovery.Resource = PrivateAttr()
    _service: discovery.Resource = PrivateAttr()
    _log: Logger = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)

        if self.service_account_file_path is not None:
            credentials, _ = auth.load_credentials_from_file(
                filename=self.service_account_file_path, scopes=self.scopes
            )
        else:
            credentials, _ = auth.default(scopes=self.scopes)

        self._drive = discovery.build(
            serviceName="drive", version=self.version, credentials=credentials
        )
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        self._service = self._drive.files()

    def get_modified_times(
        self, file_ids: list[str], *, logger: Logger | None = None
    ) -> dict[str, float]:
        """Batch Drive files.get for modifiedTime across many file IDs.

        Issues one HTTP POST to /batch containing one files.get sub-request per
        file ID. Returns a dict mapping file_id to POSIX timestamp.

        https://developers.google.com/drive/api/reference/rest/v3/files/get
        https://developers.google.com/api-client-library/python/guide/batch

        Per-file failures (4xx or 5xx) are logged and omitted from the result
        dict so one bad sheet does not break the batch — callers detect by
        checking membership. Batch-level execution failures (network, auth)
        propagate from batch.execute().

        Callers should pass `logger=context.log` from a sensor or schedule so
        warnings land in the tick log. Defaults to the resource's
        InitResourceContext logger, which may not surface in sensor tick output.
        """
        results: dict[str, float] = {}
        log = logger if logger is not None else self._log

        def _callback(
            request_id: str,
            response: dict[str, str] | None,
            exception: HttpError | None,
        ) -> None:
            if exception is not None:
                log.warning(
                    f"files.get({request_id}) failed with "
                    f"{exception.resp.status}: {exception}"
                )
                return
            modified_time = check.not_none(value=response)["modifiedTime"]
            results[request_id] = datetime.fromisoformat(modified_time).timestamp()

        # trunk-ignore(pyright/reportAttributeAccessIssue)
        batch = self._drive.new_batch_http_request(callback=_callback)
        for file_id in file_ids:
            batch.add(
                # trunk-ignore(pyright/reportAttributeAccessIssue)
                self._service.get(fileId=file_id, fields="modifiedTime"),
                request_id=file_id,
            )
        batch.execute()

        return results

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
            fields=fields,
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
        files: list[dict] | None = None,
        min_modified_time: datetime | None = None,
        _modified_time_q_suffix: str = "",
    ) -> list[dict]:
        if exclude is None:
            exclude = []

        if files is None:
            files = []

        if not _modified_time_q_suffix and min_modified_time is not None:
            _modified_time_q_suffix = (
                f" and (mimeType = 'application/vnd.google-apps.folder'"
                f" or modifiedTime > '"
                f"{min_modified_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}')"
            )

        if file_path in exclude:
            return files

        q = f"'{folder_id}' in parents and trashed = false{_modified_time_q_suffix}"

        self._log.info(f"Listing of all files under {file_path}")
        files_list = self.files_list(
            corpora=corpora,
            drive_id=drive_id,
            include_items_from_all_drives=include_items_from_all_drives,
            q=q,
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
                    _modified_time_q_suffix=_modified_time_q_suffix,
                )
            else:
                file["path"] = f"{file_path}/{file['name']}"
                file["size"] = int(file["size"])
                file["modified_timestamp"] = datetime.strptime(
                    file["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
                ).timestamp()

                files.append(file)

        return files
