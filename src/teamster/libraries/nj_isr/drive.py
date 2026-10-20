import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import google.auth
import google.auth.credentials
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from teamster.libraries.nj_isr.models import MissingFolderError

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME = "application/vnd.google-apps.folder"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
PDF_MIME = "application/pdf"

ALL_REPORTS_TAB = "All reports"

_FILE_FIELDS = "id,name,webViewLink"
_NUM_RETRIES = 5
_FORMULA_PREFIXES = ("=", "+", "-", "@")
_HYPERLINK_PREFIX = "=HYPERLINK("
# The banner rows on All reports. Sheets refuses to freeze every row of a grid.
_FROZEN_ROWS = 5
_UNREADABLE = {
    403: "Drive returned 403 for {id}: the service account can see it but may not "
    "read it",
    404: "Drive returned 404 for {id}: it does not exist, or the service account "
    "cannot see it",
}


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    web_view_link: str


class DriveApi(Protocol):
    def get(self, file_id: str) -> DriveFile: ...

    def list_children(self, parent_id: str, mime_type: str) -> list[DriveFile]: ...

    def find_child(
        self, parent_id: str, name: str, mime_type: str
    ) -> DriveFile | None: ...

    def create(
        self,
        parent_id: str,
        name: str,
        mime_type: str,
        *,
        media_path: Path | None = None,
        properties: Mapping[str, str] | None = None,
        shortcut_target: str | None = None,
    ) -> DriveFile: ...

    def update_media(self, file_id: str, media_path: Path) -> DriveFile: ...

    def list_tagged(self, parent_id: str, key: str, value: str) -> list[DriveFile]: ...

    def trash(self, file_id: str) -> None: ...

    def readers(self, file_id: str) -> list[str]: ...

    def write_sheet(
        self, spreadsheet_id: str, tabs: Mapping[str, list[list[str]]]
    ) -> None: ...


def escape_query_value(value: str) -> str:
    """Escapes a value for use inside single quotes in a Drive search query."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def folder_id_from_url(url_or_id: str) -> str:
    """Returns the folder ID from a Drive folder URL, or the input if it is an ID."""
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", url_or_id)

    return match.group(1) if match else url_or_id.strip()


def load_credentials() -> google.auth.credentials.Credentials:
    """Returns the environment's default Google credentials with the Drive scope."""
    return google.auth.default(scopes=[DRIVE_SCOPE])[0]


def _to_drive_file(raw: Mapping[str, str]) -> DriveFile:
    return DriveFile(
        id=raw["id"], name=raw["name"], web_view_link=raw.get("webViewLink", "")
    )


def _quote_tab(tab: str) -> str:
    return "'" + tab.replace("'", "''") + "'"


def _sheet_safe(cell: str) -> str:
    """Stops USER_ENTERED from evaluating a cell as a formula.

    Cells that start with a formula character get a leading apostrophe, which
    Sheets treats as "text". Only the report links this module writes
    deliberately (`=HYPERLINK(...)`) pass through.
    """
    if (
        isinstance(cell, str)
        and cell.startswith(_FORMULA_PREFIXES)
        and not cell.startswith(_HYPERLINK_PREFIX)
    ):
        return "'" + cell

    return cell


def _all_reports_format_requests(sheet_id: int) -> list[dict]:
    def repeat_cell(end_row: int, start_row: int, text_format: dict) -> dict:
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                },
                "cell": {"userEnteredFormat": {"textFormat": text_format}},
                "fields": "userEnteredFormat.textFormat."
                + ",userEnteredFormat.textFormat.".join(text_format),
            }
        }

    return [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": _FROZEN_ROWS},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        repeat_cell(start_row=0, end_row=4, text_format={"fontSize": 14}),
        repeat_cell(start_row=0, end_row=1, text_format={"bold": True}),
        repeat_cell(start_row=4, end_row=5, text_format={"bold": True}),
    ]


def _layout_requests(
    sheet_ids: Mapping[str, int], tabs: Mapping[str, list[list[str]]]
) -> list[dict]:
    """Deletes tabs not in `tabs`, orders the rest, and sizes each grid.

    Tabs move in order of their target index, so each move is to a lower index
    or to where the tab already is. Sheets counts a move to a higher index
    against the positions before the move, which this order never needs.
    """
    deletes = [
        {"deleteSheet": {"sheetId": sheet_id}}
        for title, sheet_id in sheet_ids.items()
        if title not in tabs
    ]
    moves = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_ids[tab], "index": index},
                "fields": "index",
            }
        }
        for index, tab in enumerate(tabs)
    ]
    grids = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_ids[tab],
                    "gridProperties": {
                        "rowCount": max(
                            len(rows),
                            _FROZEN_ROWS + 1 if tab == ALL_REPORTS_TAB else 1,
                        ),
                        "columnCount": max([1, *(len(row) for row in rows)]),
                    },
                },
                "fields": "gridProperties.rowCount,gridProperties.columnCount",
            }
        }
        for tab, rows in tabs.items()
    ]
    return deletes + moves + grids


class GoogleDriveApi:
    """Drive v3 and Sheets v4 calls over one set of credentials.

    Every call that targets a file passes `supportsAllDrives=True`; without it,
    files in a shared drive return 404 even when the caller has access.
    """

    def __init__(self, credentials: google.auth.credentials.Credentials) -> None:
        self._drive: Any = discovery.build(
            serviceName="drive", version="v3", credentials=credentials
        )
        self._sheets: Any = discovery.build(
            serviceName="sheets", version="v4", credentials=credentials
        )

    def _list(self, q: str) -> list[DriveFile]:
        files = self._drive.files()
        found: list[DriveFile] = []

        request = files.list(
            q=q,
            fields=f"nextPageToken,files({_FILE_FIELDS})",
            corpora="allDrives",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )

        while request is not None:
            response = request.execute(num_retries=_NUM_RETRIES)
            found.extend(_to_drive_file(f) for f in response.get("files", []))
            request = files.list_next(request, response)

        return found

    def get(self, file_id: str) -> DriveFile:
        """Reads one file or folder.

        Raises:
            MissingFolderError: If Drive answers 403 or 404, which for a folder
                in a shared drive means the service account cannot open it.
        """
        try:
            response = (
                self._drive.files()
                .get(fileId=file_id, fields=_FILE_FIELDS, supportsAllDrives=True)
                .execute(num_retries=_NUM_RETRIES)
            )
        except HttpError as e:
            if e.resp.status in _UNREADABLE:
                raise MissingFolderError(
                    _UNREADABLE[e.resp.status].format(id=file_id)
                ) from e

            raise

        return _to_drive_file(response)

    def list_children(self, parent_id: str, mime_type: str) -> list[DriveFile]:
        return self._list(
            f"'{escape_query_value(parent_id)}' in parents"
            f" and mimeType = '{mime_type}'"
            " and trashed = false"
        )

    def find_child(self, parent_id: str, name: str, mime_type: str) -> DriveFile | None:
        matches = self._list(
            f"'{escape_query_value(parent_id)}' in parents"
            f" and name = '{escape_query_value(name)}'"
            f" and mimeType = '{mime_type}'"
            " and trashed = false"
        )

        if len(matches) > 1:
            raise MissingFolderError(
                f"{len(matches)} items named {name!r} in Drive folder {parent_id};"
                " expected 1"
            )

        return matches[0] if matches else None

    def create(
        self,
        parent_id: str,
        name: str,
        mime_type: str,
        *,
        media_path: Path | None = None,
        properties: Mapping[str, str] | None = None,
        shortcut_target: str | None = None,
    ) -> DriveFile:
        body: dict[str, Any] = {
            "name": name,
            "mimeType": mime_type,
            "parents": [parent_id],
        }

        if properties:
            body["properties"] = dict(properties)

        if shortcut_target is not None:
            body["shortcutDetails"] = {"targetId": shortcut_target}

        kwargs: dict[str, Any] = {
            "body": body,
            "fields": _FILE_FIELDS,
            "supportsAllDrives": True,
        }

        if media_path is not None:
            kwargs["media_body"] = MediaFileUpload(
                str(media_path), mimetype=PDF_MIME, resumable=True
            )

        response = (
            self._drive.files().create(**kwargs).execute(num_retries=_NUM_RETRIES)
        )

        return _to_drive_file(response)

    def update_media(self, file_id: str, media_path: Path) -> DriveFile:
        response = (
            self._drive.files()
            .update(
                fileId=file_id,
                media_body=MediaFileUpload(
                    str(media_path), mimetype=PDF_MIME, resumable=True
                ),
                fields=_FILE_FIELDS,
                supportsAllDrives=True,
            )
            .execute(num_retries=_NUM_RETRIES)
        )

        return _to_drive_file(response)

    def list_tagged(self, parent_id: str, key: str, value: str) -> list[DriveFile]:
        return self._list(
            f"'{escape_query_value(parent_id)}' in parents"
            f" and properties has {{ key='{escape_query_value(key)}'"
            f" and value='{escape_query_value(value)}' }}"
            " and trashed = false"
        )

    def trash(self, file_id: str) -> None:
        self._drive.files().update(
            fileId=file_id,
            body={"trashed": True},
            fields="id",
            supportsAllDrives=True,
        ).execute(num_retries=_NUM_RETRIES)

    def readers(self, file_id: str) -> list[str]:
        permissions = self._drive.permissions()
        found: list[str] = []

        request = permissions.list(
            fileId=file_id,
            supportsAllDrives=True,
            fields="nextPageToken,permissions(role,emailAddress,domain,type)",
        )

        while request is not None:
            response = request.execute(num_retries=_NUM_RETRIES)
            found.extend(
                f"{p['role']}: {p.get('emailAddress') or p.get('domain') or p['type']}"
                for p in response.get("permissions", [])
            )
            request = permissions.list_next(request, response)

        return found

    def write_sheet(
        self, spreadsheet_id: str, tabs: Mapping[str, list[list[str]]]
    ) -> None:
        """Makes the spreadsheet hold exactly `tabs`, in order, and writes them.

        The command owns the spreadsheet, so a tab not named in `tabs`,
        including the default tab of a new spreadsheet, is deleted. Missing tabs
        are added first, so the spreadsheet never has 0 tabs. Each grid is sized
        to its values, and formatting is applied to `All reports`.
        """
        spreadsheets = self._sheets.spreadsheets()

        existing = spreadsheets.get(
            spreadsheetId=spreadsheet_id, fields="sheets.properties"
        ).execute(num_retries=_NUM_RETRIES)
        sheet_ids: dict[str, int] = {
            s["properties"]["title"]: s["properties"]["sheetId"]
            for s in existing.get("sheets", [])
        }

        missing = [tab for tab in tabs if tab not in sheet_ids]

        if missing:
            added = spreadsheets.batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [
                        {"addSheet": {"properties": {"title": tab}}} for tab in missing
                    ]
                },
            ).execute(num_retries=_NUM_RETRIES)

            for tab, reply in zip(missing, added.get("replies", []), strict=False):
                sheet_ids[tab] = reply["addSheet"]["properties"]["sheetId"]

        spreadsheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": _layout_requests(sheet_ids, tabs)},
        ).execute(num_retries=_NUM_RETRIES)

        values = spreadsheets.values()

        for tab, rows in tabs.items():
            values.clear(
                spreadsheetId=spreadsheet_id, range=_quote_tab(tab), body={}
            ).execute(num_retries=_NUM_RETRIES)
            values.update(
                spreadsheetId=spreadsheet_id,
                range=f"{_quote_tab(tab)}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [[_sheet_safe(cell) for cell in row] for row in rows]},
            ).execute(num_retries=_NUM_RETRIES)

        if ALL_REPORTS_TAB in tabs:
            spreadsheets.batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": _all_reports_format_requests(sheet_ids[ALL_REPORTS_TAB])
                },
            ).execute(num_retries=_NUM_RETRIES)
