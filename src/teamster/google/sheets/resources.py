import pathlib

import google.auth
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from gspread.auth import authorize, service_account
from gspread.client import Client
from gspread.exceptions import SpreadsheetNotFound
from gspread.utils import rowcol_to_a1
from pydantic import PrivateAttr


class GoogleSheetsResource(ConfigurableResource):
    service_account_file_path: str | None = None

    _client: Client = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)

        if self.service_account_file_path is not None:
            self._client = service_account(
                filename=pathlib.Path(self.service_account_file_path)
            )
        else:
            credentials, project_id = google.auth.default(
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ]
            )

            self._client = authorize(credentials=credentials)

    def open(self, **kwargs):
        kwargs_keys = kwargs.keys()

        if "title" in kwargs_keys:
            return self._client.open(**kwargs)
        elif "sheet_id" in kwargs_keys:
            return self._client.open_by_key(key=kwargs["sheet_id"])
        elif "url" in kwargs_keys:
            return self._client.open_by_url(**kwargs)

    def open_or_create_sheet(self, **kwargs):
        try:
            spreadsheet = self.open(**kwargs)
        except SpreadsheetNotFound as e:
            self._log.warning(e)
            self._log.info("Creating new Sheet")

            spreadsheet = self._client.create(**kwargs)

        return spreadsheet

    @staticmethod
    def rowcol_to_a1(row, col):
        return rowcol_to_a1(row=row, col=col)
