import google.auth
import gspread
from dagster import Field, String, resource


class GoogleSheets:
    def __init__(self, folder_id, logger):
        self.folder_id = folder_id
        self.log = logger
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        credentials, project_id = google.auth.default(scopes=self.scopes)
        self.client = gspread.authorize(credentials)

    def create_spreadsheet(self, title):
        return self.client.create(title=title, folder_id=self.folder_id)

    def open_spreadsheet(self, title, create=False):
        try:
            spreadsheet = self.client.open(title=title, folder_id=self.folder_id)
            self.log.info(f"Opened: '{spreadsheet.title}' from {spreadsheet.url}.")
            return spreadsheet
        except gspread.exceptions.SpreadsheetNotFound as xc:
            if create:
                spreadsheet = self.create_spreadsheet(title=title)
                self.log.info(f"Created: '{spreadsheet.title}' at {spreadsheet.url}.")
                return spreadsheet
            else:
                raise xc
        except Exception as xc:
            raise xc

    def get_named_range(self, spreadsheet, range_name):
        named_ranges = spreadsheet.list_named_ranges()

        named_range_match = [nr for nr in named_ranges if nr["name"] == range_name]

        return named_range_match[0] if named_range_match else None

    def update_named_range(self, data, spreadsheet_name, range_name):
        spreadsheet = self.open_spreadsheet(title=spreadsheet_name, create=True)

        named_range = self.get_named_range(
            spreadsheet=spreadsheet, range_name=range_name
        )

        if named_range:
            worksheet = spreadsheet.get_worksheet_by_id(
                id=named_range["range"].get("sheetId", 0)
            )

            named_range_id = named_range.get("namedRangeId")
            end_row_ix = named_range["range"].get("endRowIndex", 0)
            end_col_ix = named_range["range"].get("endColumnIndex", 0)
            range_area = (end_row_ix + 1) * (end_col_ix + 1)
        else:
            worksheet = spreadsheet.sheet1
            named_range_id = None
            range_area = 0

        nrows, ncols = data["shape"]
        nrows = nrows + 1  # header row
        data_area = nrows * ncols

        # resize worksheet
        worksheet_area = worksheet.row_count * worksheet.col_count
        if worksheet_area != data_area:
            self.log.debug(f"Resizing worksheet area to {nrows}x{ncols}.")
            worksheet.resize(rows=nrows, cols=ncols)

        # resize named range
        if range_area != data_area:
            start_cell = gspread.utils.rowcol_to_a1(1, 1)
            end_cell = gspread.utils.rowcol_to_a1(nrows, ncols)

            self.log.debug(
                f"Resizing named range '{range_name}' to {start_cell}:{end_cell}."
            )
            worksheet.delete_named_range(named_range_id=named_range_id)
            worksheet.define_named_range(
                name=f"{start_cell}:{end_cell}", range_name=range_name
            )

        self.log.debug(f"Clearing '{range_name}' values.")
        worksheet.batch_clear([range_name])

        self.log.info(f"Updating '{range_name}': {data_area} cells.")
        worksheet.update(range_name, [data["columns"]] + data["data"])


@resource(config_schema={"folder_id": Field(String)})
def google_sheets(context):
    return GoogleSheets(
        folder_id=context.resource_config["folder_id"], logger=context.log
    )
