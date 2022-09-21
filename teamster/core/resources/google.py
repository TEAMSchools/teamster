import dagster._check as check
import google.auth
import gspread
from dagster import Field, String, StringSource, resource
from dagster._utils import merge_dicts
from dagster_gcp.gcs.file_manager import GCSFileManager
from dagster_gcp.gcs.resources import GCS_CLIENT_CONFIG, _gcs_client_from_config


class GCSFileManager(GCSFileManager):
    def __init__(self, logger, client, gcs_bucket, gcs_base_key):
        self.log = logger

        super().__init__(client, gcs_bucket, gcs_base_key)

    def blob_exists(self, ext=None, key=None):
        key = check.opt_str_param(key, "key")

        gcs_key = self.get_full_key(key + (("." + ext) if ext is not None else ""))
        self.log.debug(gcs_key)

        blobs = self._client.list_blobs(bucket_or_name=self._gcs_bucket)
        self.log.debug(list(blobs))

        return True if [b for b in blobs if b.name == gcs_key] else False

    def download_as_bytes(self, file_handle):
        bucket_obj = self._client.bucket(file_handle.gcs_bucket)
        return bucket_obj.blob(file_handle.gcs_key).download_as_bytes()


@resource(
    merge_dicts(
        GCS_CLIENT_CONFIG,
        {
            "gcs_bucket": Field(StringSource),
            "gcs_prefix": Field(
                StringSource, is_required=False, default_value="dagster"
            ),
        },
    )
)
def gcs_file_manager(context):
    """FileManager that provides abstract access to GCS.

    Implements the :py:class:`~dagster._core.storage.file_manager.FileManager` API.
    """
    gcs_client = _gcs_client_from_config(context.resource_config)
    return GCSFileManager(
        logger=context.log,
        client=gcs_client,
        gcs_bucket=context.resource_config["gcs_bucket"],
        gcs_base_key=context.resource_config["gcs_prefix"],
    )


class GoogleSheets(object):
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
            return self.client.open(title=title, folder_id=self.folder_id)
        except gspread.exceptions.SpreadsheetNotFound as xc:
            if create:
                spreadsheet = self.create_spreadsheet(title=title)
                self.log.info(
                    f"Created Spreadsheet '{spreadsheet.title}' at {spreadsheet.url}."
                )
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
            self.log.info(f"Resizing worksheet area to {nrows}x{ncols}.")
            worksheet.resize(rows=nrows, cols=ncols)

        # resize named range
        if range_area != data_area:
            start_cell = gspread.utils.rowcol_to_a1(1, 1)
            end_cell = gspread.utils.rowcol_to_a1(nrows, ncols)

            self.log.info(
                f"Resizing named range '{range_name}' to {start_cell}:{end_cell}."
            )
            worksheet.delete_named_range(named_range_id=named_range_id)
            worksheet.define_named_range(
                name=f"{start_cell}:{end_cell}", range_name=range_name
            )

        self.log.info(f"Clearing '{range_name}' values.")
        worksheet.batch_clear([range_name])

        self.log.info(f"Updating '{range_name}': {data_area} cells.")
        worksheet.update(range_name, [data["columns"]] + data["data"])


@resource(config_schema={"folder_id": Field(String)})
def google_sheets(context):
    return GoogleSheets(
        folder_id=context.resource_config["folder_id"], logger=context.log
    )
