import copy
import pathlib
from typing import Union
from urllib.parse import urlparse

import fastavro
import google.auth
import gspread
import pendulum
from dagster import (
    Field,
    InputContext,
    MultiPartitionKey,
    OutputContext,
    String,
    StringSource,
    io_manager,
    resource,
)
from dagster._utils.backoff import backoff
from dagster_gcp.gcs.io_manager import PickledObjectGCSIOManager
from google.api_core.exceptions import Forbidden, ServiceUnavailable, TooManyRequests

from teamster.core.utils.classes import FiscalYear


def parse_date_partition_key(partition_key):
    fiscal_year = FiscalYear(datetime=partition_key, start_month=7).fiscal_year

    return [
        f"_dagster_partition_fiscal_year={fiscal_year}",
        f"_dagster_partition_date={partition_key.to_date_string()}",
        f"_dagster_partition_hour={partition_key.format('HH')}",
        f"_dagster_partition_minute={partition_key.format('mm')}",
    ]


class FilepathGCSIOManager(PickledObjectGCSIOManager):
    def _get_path(self, context: Union[InputContext, OutputContext]) -> str:
        if context.has_asset_key:
            path = copy.deepcopy(context.asset_key.path)

            if context.has_asset_partitions:
                context.log.debug(context.asset_partitions_def)
                path.extend(
                    parse_date_partition_key(pendulum.parse(text=context.partition_key))
                )

            path.append("data")
        else:
            parts = context.get_identifier()
            run_id = parts[0]
            output_parts = parts[1:]

            path = ["storage", run_id, "files", *output_parts]

        return "/".join([self.prefix, *path])

    def handle_output(self, context: OutputContext, file_path: pathlib.Path):
        key = self._get_path(context)

        if self._has_object(key):
            context.log.warning(f"Removing existing GCS key: {key}")
            self._rm_object(key)

        context.log.info(
            f"Uploading {file_path} to GCS object at: {self._uri_for_key(key)}"
        )

        backoff(
            self.bucket_obj.blob(key).upload_from_filename,
            args=[file_path],
            retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
        )

    def load_input(self, context: InputContext):
        if isinstance(context.dagster_type.typing_type, type(None)):
            return None

        key = self._get_path(context)

        return [urlparse(self._uri_for_key(key))]


class AvroGCSIOManager(PickledObjectGCSIOManager):
    def _get_path(self, context: Union[InputContext, OutputContext]) -> str:
        if context.has_asset_key:
            path = copy.deepcopy(context.asset_key.path)

            if context.has_asset_partitions:
                if isinstance(context.partition_key, MultiPartitionKey):
                    for (
                        dimension,
                        key,
                    ) in context.partition_key.keys_by_dimension.items():
                        if dimension == "date":
                            path.extend(
                                parse_date_partition_key(pendulum.parse(text=key))
                            )
                        else:
                            path.append(f"_dagster_partition_{dimension}={key}")
                else:
                    path.append(f"_dagster_partition_key={context.partition_key}")

            path.append("data")
        else:
            parts = context.get_identifier()
            run_id = parts[0]
            output_parts = parts[1:]

            path = ["storage", run_id, "files", *output_parts]

        return "/".join([self.prefix, *path])

    def handle_output(self, context: OutputContext, obj):
        records, schema = obj

        key = self._get_path(context)

        if self._has_object(key):
            context.log.warning(f"Removing existing GCS key: {key}")
            self._rm_object(key)

        file_path = pathlib.Path(key)

        context.log.debug(f"Saving output to Avro file: {file_path}")
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open(mode="wb") as fo:
            fastavro.writer(
                fo=fo,
                schema=fastavro.parse_schema(schema),
                records=records,
                codec="snappy",
            )

        context.log.info(
            f"Uploading {file_path} to GCS object at: {self._uri_for_key(key)}"
        )

        backoff(
            self.bucket_obj.blob(key).upload_from_filename,
            args=[file_path],
            retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
        )

    def load_input(self, context: InputContext):
        if isinstance(context.dagster_type.typing_type, type(None)):
            return None

        key = self._get_path(context)

        return [urlparse(self._uri_for_key(key))]


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


@io_manager(
    config_schema={
        "gcs_bucket": Field(config=StringSource),
        "gcs_prefix": Field(
            config=StringSource, is_required=False, default_value="dagster"
        ),
    },
    required_resource_keys={"gcs"},
)
def gcs_filepath_io_manager(init_context):
    client = init_context.resources.gcs
    filename_io_manager = FilepathGCSIOManager(
        init_context.resource_config["gcs_bucket"],
        client,
        init_context.resource_config["gcs_prefix"],
    )
    return filename_io_manager


@io_manager(
    config_schema={
        "gcs_bucket": Field(config=StringSource),
        "gcs_prefix": Field(
            config=StringSource, is_required=False, default_value="dagster"
        ),
    },
    required_resource_keys={"gcs"},
)
def gcs_avro_io_manager(init_context):
    return AvroGCSIOManager(
        bucket=init_context.resource_config["gcs_bucket"],
        client=init_context.resources.gcs,
        prefix=init_context.resource_config["gcs_prefix"],
    )


@resource(config_schema={"folder_id": Field(String)})
def google_sheets(context):
    return GoogleSheets(
        folder_id=context.resource_config["folder_id"], logger=context.log
    )
