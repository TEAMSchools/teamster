from pathlib import Path
from unittest.mock import MagicMock

import httplib2
import pytest
from google.auth.credentials import AnonymousCredentials, Credentials, Scoped
from googleapiclient.errors import HttpError

from teamster.libraries.nj_isr.drive import (
    DRIVE_SCOPE,
    FOLDER_MIME,
    PDF_MIME,
    SHORTCUT_MIME,
    DriveFile,
    GoogleDriveApi,
    escape_query_value,
    folder_id_from_url,
    load_credentials,
)
from teamster.libraries.nj_isr.models import MissingFolderError


@pytest.fixture
def api() -> GoogleDriveApi:
    api = GoogleDriveApi(AnonymousCredentials())
    api._drive = MagicMock()
    api._sheets = MagicMock()
    # a single page of results unless a test says otherwise
    api._drive.files.return_value.list_next.return_value = None
    return api


def _list_returns(api: GoogleDriveApi, files: list[dict]) -> None:
    list_request = api._drive.files.return_value.list.return_value
    list_request.execute.return_value = {"files": files}


def _pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.4 test")
    return path


def test_escape_query_value():
    assert escape_query_value("O'Brien Report Cards") == "O\\'Brien Report Cards"
    assert escape_query_value("a\\b") == "a\\\\b"


def test_find_child_builds_query_and_passes_all_drives(api):
    _list_returns(api, [])

    result = api.find_child("parent123", "O'Brien Report Cards", FOLDER_MIME)

    kwargs = api._drive.files.return_value.list.call_args.kwargs
    assert result is None
    assert "'parent123' in parents" in kwargs["q"]
    assert "name = 'O\\'Brien Report Cards'" in kwargs["q"]
    assert f"mimeType = '{FOLDER_MIME}'" in kwargs["q"]
    assert "trashed = false" in kwargs["q"]
    assert kwargs["supportsAllDrives"] is True
    assert kwargs["includeItemsFromAllDrives"] is True
    assert kwargs["corpora"] == "allDrives"
    assert kwargs["fields"] == "nextPageToken,files(id,name,webViewLink)"


def test_find_child_returns_the_single_match(api):
    _list_returns(api, [{"id": "a", "name": "X", "webViewLink": "https://x/a"}])

    assert api.find_child("p", "X", FOLDER_MIME) == DriveFile(
        id="a", name="X", web_view_link="https://x/a"
    )


def test_find_child_raises_on_two_matches(api):
    _list_returns(
        api,
        [
            {"id": "a", "name": "X", "webViewLink": ""},
            {"id": "b", "name": "X", "webViewLink": ""},
        ],
    )

    with pytest.raises(MissingFolderError, match="2 items named"):
        api.find_child("p", "X", FOLDER_MIME)


def test_list_follows_next_page_token(api):
    files = api._drive.files.return_value
    first_request, second_request = MagicMock(), MagicMock()
    files.list.return_value = first_request
    first_request.execute.return_value = {
        "files": [{"id": "a", "name": "X", "webViewLink": ""}],
        "nextPageToken": "t2",
    }
    second_request.execute.return_value = {
        "files": [{"id": "b", "name": "X", "webViewLink": ""}]
    }
    files.list_next.side_effect = [second_request, None]

    with pytest.raises(MissingFolderError, match="2 items named"):
        api.find_child("p", "X", FOLDER_MIME)

    assert second_request.execute.called


def test_list_tagged_queries_properties_across_pages(api):
    files = api._drive.files.return_value
    first_request, second_request = MagicMock(), MagicMock()
    files.list.return_value = first_request
    first_request.execute.return_value = {
        "files": [{"id": "a", "name": "A.pdf", "webViewLink": "la"}],
        "nextPageToken": "t2",
    }
    second_request.execute.return_value = {
        "files": [{"id": "b", "name": "B.pdf", "webViewLink": "lb"}]
    }
    files.list_next.side_effect = [second_request, None]

    result = api.list_tagged("folder1", "isr_key", "it's")

    kwargs = files.list.call_args.kwargs
    assert "'folder1' in parents" in kwargs["q"]
    assert "properties has { key='isr_key' and value='it\\'s' }" in kwargs["q"]
    assert "trashed = false" in kwargs["q"]
    assert kwargs["supportsAllDrives"] is True
    assert kwargs["corpora"] == "allDrives"
    assert [f.id for f in result] == ["a", "b"]


def test_create_sends_parents_tag_and_shortcut(api):
    api._drive.files.return_value.create.return_value.execute.return_value = {
        "id": "new1",
        "name": "00 - Find",
        "webViewLink": "https://x/new1",
    }

    result = api.create("p", "00 - Find", SHORTCUT_MIME, shortcut_target="sheet1")

    kwargs = api._drive.files.return_value.create.call_args.kwargs
    body = kwargs["body"]
    assert body["parents"] == ["p"]
    assert body["name"] == "00 - Find"
    assert body["mimeType"] == SHORTCUT_MIME
    assert body["shortcutDetails"] == {"targetId": "sheet1"}
    assert "properties" not in body
    assert kwargs["supportsAllDrives"] is True
    assert "media_body" not in kwargs
    assert result == DriveFile(
        id="new1", name="00 - Find", web_view_link="https://x/new1"
    )


def test_create_uploads_pdf_with_properties(api, tmp_path):
    api._drive.files.return_value.create.return_value.execute.return_value = {
        "id": "f1",
        "name": "r.pdf",
        "webViewLink": "",
    }

    api.create(
        "p",
        "r.pdf",
        PDF_MIME,
        media_path=_pdf(tmp_path / "r.pdf"),
        properties={"isr_key": "abc"},
    )

    kwargs = api._drive.files.return_value.create.call_args.kwargs
    assert kwargs["body"]["properties"] == {"isr_key": "abc"}
    assert kwargs["media_body"].mimetype() == PDF_MIME
    assert kwargs["media_body"].resumable() is True


def test_update_media_targets_the_same_id(api, tmp_path):
    api._drive.files.return_value.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "x.pdf",
        "webViewLink": "",
    }

    api.update_media("file1", _pdf(tmp_path / "x.pdf"))

    kwargs = api._drive.files.return_value.update.call_args.kwargs
    assert kwargs["fileId"] == "file1"
    assert kwargs["supportsAllDrives"] is True
    assert kwargs["media_body"].mimetype() == PDF_MIME


def test_get_reads_one_file_across_drives(api):
    files = api._drive.files.return_value
    files.get.return_value.execute.return_value = {
        "id": "root1",
        "name": "Test root",
        "webViewLink": "https://x/root1",
    }

    assert api.get("root1") == DriveFile(
        id="root1", name="Test root", web_view_link="https://x/root1"
    )
    kwargs = files.get.call_args.kwargs
    assert kwargs == {
        "fileId": "root1",
        "fields": "id,name,webViewLink",
        "supportsAllDrives": True,
    }


def test_get_turns_a_404_into_a_missing_folder_error(api):
    files = api._drive.files.return_value
    files.get.return_value.execute.side_effect = HttpError(
        httplib2.Response({"status": 404}), b"not found"
    )

    with pytest.raises(MissingFolderError, match="404.*cannot see"):
        api.get("root1")


def test_get_reraises_other_http_errors(api):
    files = api._drive.files.return_value
    files.get.return_value.execute.side_effect = HttpError(
        httplib2.Response({"status": 500}), b"boom"
    )

    with pytest.raises(HttpError):
        api.get("root1")


def test_list_children_lists_one_mime_type(api):
    _list_returns(api, [{"id": "a", "name": "Newark", "webViewLink": ""}])

    result = api.list_children("root1", FOLDER_MIME)

    q = api._drive.files.return_value.list.call_args.kwargs["q"]
    assert "'root1' in parents" in q
    assert f"mimeType = '{FOLDER_MIME}'" in q
    assert "trashed = false" in q
    assert [f.name for f in result] == ["Newark"]


def test_trash_marks_the_file_trashed(api):
    api.trash("file1")

    kwargs = api._drive.files.return_value.update.call_args.kwargs
    assert kwargs["fileId"] == "file1"
    assert kwargs["body"] == {"trashed": True}
    assert kwargs["supportsAllDrives"] is True


def test_readers_follows_next_page_token(api):
    permissions = api._drive.permissions.return_value
    first_request, second_request = MagicMock(), MagicMock()
    permissions.list.return_value = first_request
    first_request.execute.return_value = {
        "permissions": [{"role": "reader", "type": "domain", "domain": "a.org"}],
        "nextPageToken": "t2",
    }
    second_request.execute.return_value = {
        "permissions": [{"role": "writer", "type": "domain", "domain": "b.org"}]
    }
    permissions.list_next.side_effect = [second_request, None]

    assert api.readers("file1") == ["reader: a.org", "writer: b.org"]
    assert permissions.list.call_args.kwargs["fields"] == (
        "nextPageToken,permissions(role,emailAddress,domain,type)"
    )


def test_readers_formats_role_and_grantee(api):
    permissions = api._drive.permissions.return_value
    permissions.list_next.return_value = None
    permissions.list.return_value.execute.return_value = {
        "permissions": [
            {"role": "reader", "type": "user", "emailAddress": "a@example.org"},
            {"role": "writer", "type": "domain", "domain": "example.org"},
            {"role": "reader", "type": "anyone"},
        ]
    }

    assert api.readers("file1") == [
        "reader: a@example.org",
        "writer: example.org",
        "reader: anyone",
    ]
    kwargs = permissions.list.call_args.kwargs
    assert kwargs["fileId"] == "file1"
    assert kwargs["supportsAllDrives"] is True
    assert (
        kwargs["fields"] == "nextPageToken,permissions(role,emailAddress,domain,type)"
    )


def _sheets_with_tabs(api: GoogleDriveApi, titles: dict[str, int]) -> MagicMock:
    spreadsheets = api._sheets.spreadsheets.return_value
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [
            {"properties": {"sheetId": sheet_id, "title": title}}
            for title, sheet_id in titles.items()
        ]
    }
    return spreadsheets


def _batch_requests(spreadsheets: MagicMock) -> list[list[dict]]:
    """The request list of every batchUpdate call, in call order."""
    return [
        call.kwargs["body"]["requests"]
        for call in spreadsheets.batchUpdate.call_args_list
    ]


def test_write_sheet_adds_missing_tab_clears_and_writes(api):
    spreadsheets = _sheets_with_tabs(api, {"Sheet1": 0})
    spreadsheets.batchUpdate.return_value.execute.return_value = {
        "replies": [{"addSheet": {"properties": {"sheetId": 7, "title": "Notes"}}}]
    }

    api.write_sheet("ss1", {"Notes": [["a", "b"], ["c", "d"]]})

    get_kwargs = spreadsheets.get.call_args.kwargs
    assert get_kwargs["spreadsheetId"] == "ss1"
    assert get_kwargs["fields"] == "sheets.properties"

    # the first batchUpdate adds the tab; nothing formats a tab but All reports
    assert spreadsheets.batchUpdate.call_args_list[0].kwargs["spreadsheetId"] == "ss1"
    assert _batch_requests(spreadsheets)[0] == [
        {"addSheet": {"properties": {"title": "Notes"}}}
    ]
    assert not any(
        "repeatCell" in r for batch in _batch_requests(spreadsheets) for r in batch
    )

    values = spreadsheets.values.return_value
    assert values.clear.call_args.kwargs["spreadsheetId"] == "ss1"
    assert values.clear.call_args.kwargs["range"] == "'Notes'"
    update_kwargs = values.update.call_args.kwargs
    assert update_kwargs["spreadsheetId"] == "ss1"
    assert update_kwargs["range"] == "'Notes'!A1"
    assert update_kwargs["valueInputOption"] == "USER_ENTERED"
    assert update_kwargs["body"] == {"values": [["a", "b"], ["c", "d"]]}


def test_write_sheet_deletes_other_tabs_after_its_own_exist(api):
    spreadsheets = _sheets_with_tabs(api, {"Sheet1": 0})
    spreadsheets.batchUpdate.return_value.execute.return_value = {
        "replies": [
            {"addSheet": {"properties": {"sheetId": 9}}},
            {"addSheet": {"properties": {"sheetId": 10}}},
        ]
    }

    api.write_sheet("ss1", {"All reports": [["t"]], "About": [["a", "b"]]})

    batches = _batch_requests(spreadsheets)
    add_call = next(i for i, b in enumerate(batches) if any("addSheet" in r for r in b))
    delete_call = next(
        i for i, b in enumerate(batches) if any("deleteSheet" in r for r in b)
    )
    assert add_call < delete_call
    assert [r["deleteSheet"] for r in batches[delete_call] if "deleteSheet" in r] == [
        {"sheetId": 0}
    ]


def test_write_sheet_orders_all_reports_first_and_about_second(api):
    spreadsheets = _sheets_with_tabs(api, {"About": 5, "Sheet1": 0, "All reports": 4})

    api.write_sheet("ss1", {"All reports": [["t"]], "About": [["a", "b"]]})

    moves = [
        r["updateSheetProperties"]
        for b in _batch_requests(spreadsheets)
        for r in b
        if "updateSheetProperties" in r
        and r["updateSheetProperties"]["fields"] == "index"
    ]
    assert moves == [
        {"properties": {"sheetId": 4, "index": 0}, "fields": "index"},
        {"properties": {"sheetId": 5, "index": 1}, "fields": "index"},
    ]


def test_write_sheet_sizes_each_grid_to_its_values_before_writing(api):
    spreadsheets = _sheets_with_tabs(api, {"All reports": 4, "About": 5})
    rows = [["banner"]] * 4 + [["h"] * 9] + [["r"] * 9] * 9395
    order: list[str] = []

    def record(step: str):
        def call(**_: object) -> MagicMock:
            order.append(step)
            return MagicMock()

        return call

    spreadsheets.batchUpdate.side_effect = record("batch")
    spreadsheets.values.return_value.update.side_effect = record("values")

    api.write_sheet("ss1", {"All reports": rows, "About": [["a", "b"], ["c"]]})

    grids = {
        r["updateSheetProperties"]["properties"]["sheetId"]: r["updateSheetProperties"]
        for b in _batch_requests(spreadsheets)
        for r in b
        if "updateSheetProperties" in r
        and "rowCount" in r["updateSheetProperties"]["fields"]
    }
    assert grids[4] == {
        "properties": {
            "sheetId": 4,
            "gridProperties": {"rowCount": 9400, "columnCount": 9},
        },
        "fields": "gridProperties.rowCount,gridProperties.columnCount",
    }
    assert grids[5]["properties"]["gridProperties"] == {
        "rowCount": 2,
        "columnCount": 2,
    }
    assert order.index("batch") < order.index("values")


def test_write_sheet_keeps_a_row_below_the_frozen_banner(api):
    spreadsheets = _sheets_with_tabs(api, {"All reports": 4})

    api.write_sheet("ss1", {"All reports": [["t"]] * 5})

    grid = next(
        r["updateSheetProperties"]["properties"]["gridProperties"]
        for b in _batch_requests(spreadsheets)
        for r in b
        if "updateSheetProperties" in r
        and "rowCount" in r["updateSheetProperties"]["fields"]
    )
    assert grid == {"rowCount": 6, "columnCount": 1}


def test_write_sheet_formats_all_reports(api):
    spreadsheets = _sheets_with_tabs(api, {"All reports": 42})

    api.write_sheet("ss1", {"All reports": [["t"], ["t"], ["t"], ["t"], ["h"], ["r"]]})

    requests = _batch_requests(spreadsheets)[-1]

    freeze = next(r for r in requests if "updateSheetProperties" in r)
    assert freeze["updateSheetProperties"]["properties"] == {
        "sheetId": 42,
        "gridProperties": {"frozenRowCount": 5},
    }
    assert freeze["updateSheetProperties"]["fields"] == "gridProperties.frozenRowCount"

    repeats = [r["repeatCell"] for r in requests if "repeatCell" in r]
    font = next(r for r in repeats if "fontSize" in r["fields"])
    assert font["range"] == {
        "sheetId": 42,
        "startRowIndex": 0,
        "endRowIndex": 4,
    }
    assert font["cell"]["userEnteredFormat"]["textFormat"] == {"fontSize": 14}

    bold_ranges = [
        (r["range"]["startRowIndex"], r["range"]["endRowIndex"])
        for r in repeats
        if "bold" in r["fields"]
    ]
    assert sorted(bold_ranges) == [(0, 1), (4, 5)]
    for r in repeats:
        if "bold" in r["fields"]:
            assert r["cell"]["userEnteredFormat"]["textFormat"] == {"bold": True}


def test_write_sheet_formats_a_newly_added_all_reports_tab(api):
    spreadsheets = _sheets_with_tabs(api, {"Sheet1": 0})
    spreadsheets.batchUpdate.return_value.execute.return_value = {
        "replies": [{"addSheet": {"properties": {"sheetId": 9}}}]
    }

    api.write_sheet("ss1", {"All reports": [["t"]]})

    freeze_request = _batch_requests(spreadsheets)[-1][0]
    assert freeze_request["updateSheetProperties"]["fields"] == (
        "gridProperties.frozenRowCount"
    )
    assert freeze_request["updateSheetProperties"]["properties"]["sheetId"] == 9


def test_write_sheet_neutralises_formula_lookalikes(api):
    spreadsheets = _sheets_with_tabs(api, {"Notes": 1})
    hyperlink = '=HYPERLINK("https://x/view", "Open report")'

    api.write_sheet(
        "ss1",
        {"Notes": [["=SUM(1)", "+1", "-x", "@a", "Normal name", hyperlink]]},
    )

    body = spreadsheets.values.return_value.update.call_args.kwargs["body"]
    assert body == {
        "values": [["'=SUM(1)", "'+1", "'-x", "'@a", "Normal name", hyperlink]]
    }


def test_folder_id_from_url():
    assert (
        folder_id_from_url(
            "https://drive.google.com/drive/folders/abc123?resourcekey=0-k"
        )
        == "abc123"
    )
    assert folder_id_from_url("abc123") == "abc123"


def test_load_credentials_asks_for_drive_scope(monkeypatch):
    calls = []
    credentials = object()

    def fake_default(scopes=None):
        calls.append(scopes)
        return credentials, "teamster-332318"

    monkeypatch.setattr("google.auth.default", fake_default)

    assert load_credentials() is credentials
    assert calls == [[DRIVE_SCOPE]]


def test_load_credentials_rescopes_pinned_credentials(monkeypatch):
    rescoped = object()
    with_scopes_calls = []

    class PinnedCredentials(Scoped, Credentials):
        def refresh(self, request):
            pass

        @property
        def requires_scopes(self):
            return False

        def with_scopes(self, scopes, default_scopes=None):
            with_scopes_calls.append(scopes)
            return rescoped

    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (PinnedCredentials(), "teamster-332318"),
    )

    assert load_credentials() is rescoped
    assert with_scopes_calls == [[DRIVE_SCOPE]]
