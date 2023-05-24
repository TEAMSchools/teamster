import google.auth
import gspread
from dagster import ConfigurableResource, InitResourceContext
from gspread.utils import rowcol_to_a1
from pydantic import PrivateAttr


class GoogleSheetsResource(ConfigurableResource):
    folder_id: str
    scopes: list = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    _client: gspread.Client = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        credentials, project_id = google.auth.default(scopes=self.scopes)

        self._client = gspread.authorize(credentials=credentials)

        return super().setup_for_execution(context)

    def open_or_create_sheet(self, title):
        try:
            spreadsheet = self._client.open(title=title, folder_id=self.folder_id)
        except gspread.exceptions.SpreadsheetNotFound as e:
            context = self.get_resource_context()

            context.log.warning(e)
            context.log.info("Creating new Sheet")

            spreadsheet = self._client.create(title=title, folder_id=self.folder_id)

        return spreadsheet

    @staticmethod
    def rowcol_to_a1(row, col):
        return rowcol_to_a1(row=row, col=col)
