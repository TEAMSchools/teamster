import gzip
import json
import uuid

import google.auth
import gspread
from dagster import DagsterEventType, Field, String, StringSource
from dagster import _check as check
from dagster import io_manager, resource
from dagster._utils import merge_dicts
from dagster._utils.backoff import backoff
from dagster_gcp import GCSFileHandle
from dagster_gcp.gcs.file_manager import GCSFileManager
from dagster_gcp.gcs.io_manager import PickledObjectGCSIOManager
from dagster_gcp.gcs.resources import GCS_CLIENT_CONFIG, _gcs_client_from_config
from google.api_core.exceptions import Forbidden, TooManyRequests


class GCSIOManager(PickledObjectGCSIOManager):
    def __init__(self, bucket, client=None, prefix="dagster"):
        super().__init__(bucket, client, prefix)

    def _get_file_key(self, context):
        all_output_logs = context.step_context.instance.all_logs(
            context.run_id, of_type=DagsterEventType.STEP_OUTPUT
        )

        step_output_log = (
            [log for log in all_output_logs if log.step_key == context.step_key][0]
            if all_output_logs
            else None
        )
        if step_output_log:
            metadata = (
                step_output_log.dagster_event.event_specific_data.metadata_entries
            )
        else:
            return None

        file_key_entry = (
            [e for e in metadata if e.label == "file_key"][0] if metadata else None
        )
        if file_key_entry:
            return file_key_entry.value.text
        else:
            return None

    def _get_path(self, context):
        if context.file_key:
            return "/".join([self.prefix, context.file_key])
        else:
            parts = context.get_output_identifier(context.step_context.instance)
            run_id = parts[0]
            output_parts = parts[1:]
            return "/".join([self.prefix, "storage", run_id, "files", *output_parts])

    def load_input(self, context):
        context.upstream_output.file_key = self._get_file_key(context.upstream_output)

        key = self._get_path(context.upstream_output)
        context.log.debug(f"Loading GCS object from: {self._uri_for_key(key)}")

        bytes_obj = self.bucket_obj.blob(key).download_as_bytes()
        obj = json.loads(gzip.decompress(bytes_obj))

        return obj

    def handle_output(self, context, obj):
        context.file_key = self._get_file_key(context)

        key = self._get_path(context)

        context.log.debug(f"Writing GCS object at: {self._uri_for_key(key)}")

        if self._has_object(key):
            context.log.warning(f"Removing existing GCS key: {key}")
            self._rm_object(key)

        backoff(
            self.bucket_obj.blob(key).upload_from_string,
            args=[obj],
            retry_on=(TooManyRequests, Forbidden),
        )


@io_manager(
    config_schema={
        "gcs_bucket": Field(StringSource),
        "gcs_prefix": Field(StringSource, is_required=False, default_value="dagster"),
    },
    required_resource_keys={"gcs"},
)
def gcs_io_manager(context):
    return GCSIOManager(
        bucket=context.resource_config["gcs_bucket"],
        client=context.resources.gcs,
        prefix=context.resource_config["gcs_prefix"],
    )


class GCSFileManager(GCSFileManager):
    def __init__(self, client, gcs_bucket, gcs_base_key, logger):
        super().__init__(client, gcs_bucket, gcs_base_key)
        self.bucket_obj = self._client.bucket(self._gcs_bucket)
        self.log = logger

    def _rm_object(self, key):
        check.str_param(key, "key")
        check.param_invariant(len(key) > 0, "key")

        if self.bucket_obj.blob(key).exists():
            self.bucket_obj.blob(key).delete()

    def _has_object(self, key):
        check.str_param(key, "key")
        check.param_invariant(len(key) > 0, "key")

        key = self.get_full_key(key)
        blobs = self._client.list_blobs(self._gcs_bucket, prefix=key)

        return len(list(blobs)) > 0

    def _uri_for_key(self, key):
        check.str_param(key, "key")
        return f"gs://{self._gcs_bucket}/{key}"

    def upload_from_string(self, obj, ext=None, file_key=None):
        key = self.get_full_key(
            file_key or (str(uuid.uuid4()) + (("." + ext) if ext is not None else ""))
        )

        self.log.debug(f"Writing GCS object at: {self._uri_for_key(key=key)}")

        if self._has_object(key):
            self.log.warning(f"Removing existing GCS key: {key}")
            self._rm_object(key)

        backoff(
            self.bucket_obj.blob(key).upload_from_string,
            args=[obj],
            retry_on=(TooManyRequests, Forbidden),
        )

        return GCSFileHandle(self._gcs_bucket, key)

    def download_as_bytes(self, file_handle):
        bucket_obj = self._client.bucket(file_handle.gcs_bucket)
        return bucket_obj.blob(file_handle.gcs_key).download_as_bytes()


@resource(
    config_schema=merge_dicts(
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
    Implements the :py:class:`~dagster.core.storage.file_manager.FileManager` API.
    """
    gcs_client = _gcs_client_from_config(context.resource_config)
    return GCSFileManager(
        client=gcs_client,
        gcs_bucket=context.resource_config["gcs_bucket"],
        gcs_base_key=context.resource_config["gcs_prefix"],
        logger=context.log,
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
