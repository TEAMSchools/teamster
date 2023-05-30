import google.auth
import gspread
from dagster import ConfigurableResource, InitResourceContext
from gspread.utils import rowcol_to_a1
from pydantic import PrivateAttr


class GoogleSheetsResource(ConfigurableResource):
    service_account_file_path: str = None

    _client: gspread.Client = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        if self.service_account_file_path is not None:
            self._client = gspread.service_account(
                filename=self.service_account_file_path
            )
        else:
            credentials, project_id = google.auth.default(
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ]
            )

            self._client = gspread.authorize(credentials=credentials)

        return super().setup_for_execution(context)

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
        except gspread.exceptions.SpreadsheetNotFound as e:
            context = self.get_resource_context()

            context.log.warning(e)
            context.log.info("Creating new Sheet")

            spreadsheet = self._client.create(**kwargs)

        return spreadsheet

    @staticmethod
    def rowcol_to_a1(row, col):
        return rowcol_to_a1(row=row, col=col)
