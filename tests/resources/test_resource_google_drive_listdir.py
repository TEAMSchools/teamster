from unittest.mock import MagicMock

from teamster.libraries.google.drive.resources import GoogleDriveResource


def _build_drive_resource() -> GoogleDriveResource:
    resource = GoogleDriveResource()
    resource._log = MagicMock()
    resource._service = MagicMock()
    return resource


def _mock_files_list(resource: GoogleDriveResource, responses: dict[str, list]):
    """Mock files_list to return different results based on the query.

    Simulates Drive API server-side filtering: applies folder parent match and
    modifiedTime filters parsed from the ``q`` parameter, mirroring the combined
    query that ``files_list_recursive`` builds when ``min_modified_time`` is set.

    Args:
        resource: The GoogleDriveResource to mock.
        responses: Dict mapping folder_id to list of file dicts.
    """
    import re

    def side_effect(**kwargs) -> list[dict]:
        q = kwargs.get("q", "")

        matched_files: list[dict] = []
        for folder_id, files in responses.items():
            if f"'{folder_id}' in parents" in q:
                matched_files = files
                break

        # Parse optional modifiedTime filter from q, e.g.:
        # "... and (mimeType = 'application/vnd.google-apps.folder'
        #           or modifiedTime > '2026-03-01T00:00:00.000Z')"
        modified_time_match = re.search(r"modifiedTime > '([^']+)'", q)
        if modified_time_match is None:
            return matched_files

        min_time = modified_time_match.group(1)
        folder_mime = "application/vnd.google-apps.folder"
        return [
            f
            for f in matched_files
            if f["mimeType"] == folder_mime or f["modifiedTime"] > min_time
        ]

    # ConfigurableResource is a frozen pydantic model — use object.__setattr__
    # to bypass the frozen constraint when monkey-patching a method for testing.
    object.__setattr__(resource, "files_list", MagicMock(side_effect=side_effect))


COMMON_KWARGS = {
    "corpora": "drive",
    "drive_id": "fake-drive-id",
    "include_items_from_all_drives": True,
    "supports_all_drives": True,
    "fields": "files(id,name,mimeType,modifiedTime,size)",
}


def test_min_modified_time_filters_old_files():
    resource = _build_drive_resource()

    _mock_files_list(
        resource,
        {
            "root-folder": [
                {
                    "id": "f1",
                    "name": "old.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2026-01-01T00:00:00.000Z",
                    "size": "100",
                },
                {
                    "id": "f2",
                    "name": "new.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2026-04-01T00:00:00.000Z",
                    "size": "200",
                },
            ],
        },
    )

    files = resource.files_list_recursive(
        **COMMON_KWARGS,
        folder_id="root-folder",
        file_path="/test",
        min_modified_time="2026-03-01T00:00:00.000Z",
    )

    assert len(files) == 1
    assert files[0]["name"] == "new.csv"


def test_min_modified_time_preserves_folders():
    resource = _build_drive_resource()

    _mock_files_list(
        resource,
        {
            "root-folder": [
                {
                    "id": "subfolder",
                    "name": "subdir",
                    "mimeType": "application/vnd.google-apps.folder",
                    "modifiedTime": "2025-01-01T00:00:00.000Z",
                    "size": "0",
                },
            ],
            "subfolder": [
                {
                    "id": "f1",
                    "name": "recent.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2026-04-01T00:00:00.000Z",
                    "size": "100",
                },
            ],
        },
    )

    files = resource.files_list_recursive(
        **COMMON_KWARGS,
        folder_id="root-folder",
        file_path="/test",
        min_modified_time="2026-03-01T00:00:00.000Z",
    )

    assert len(files) == 1
    assert files[0]["name"] == "recent.csv"
    assert files[0]["path"] == "/test/subdir/recent.csv"


def test_min_modified_time_none_returns_all():
    resource = _build_drive_resource()

    _mock_files_list(
        resource,
        {
            "root-folder": [
                {
                    "id": "f1",
                    "name": "old.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2025-01-01T00:00:00.000Z",
                    "size": "100",
                },
                {
                    "id": "f2",
                    "name": "new.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2026-04-01T00:00:00.000Z",
                    "size": "200",
                },
            ],
        },
    )

    files = resource.files_list_recursive(
        **COMMON_KWARGS,
        folder_id="root-folder",
        file_path="/test",
    )

    assert len(files) == 2


def test_min_modified_time_query_construction():
    """Verify the Drive API query includes the combined filter."""
    resource = _build_drive_resource()

    _mock_files_list(resource, {"root-folder": []})

    resource.files_list_recursive(
        **COMMON_KWARGS,
        folder_id="root-folder",
        file_path="/test",
        min_modified_time="2026-03-01T00:00:00.000Z",
    )

    # trunk-ignore(pyright/reportAttributeAccessIssue): files_list is a MagicMock
    call_kwargs = resource.files_list.call_args_list[0].kwargs
    expected_q = (
        "'root-folder' in parents and trashed = false"
        " and (mimeType = 'application/vnd.google-apps.folder'"
        " or modifiedTime > '2026-03-01T00:00:00.000Z')"
    )
    assert call_kwargs["q"] == expected_q
