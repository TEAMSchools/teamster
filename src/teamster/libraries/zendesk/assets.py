import pathlib
from datetime import datetime

from dagster import (
    AssetExecutionContext,
    MonthlyPartitionsDefinition,
    Output,
    asset,
    check,
)
from dateutil.relativedelta import relativedelta
from fastavro import block_reader, parse_schema, writer
from zenpy.lib.api_objects import BaseObject  # type: ignore
from zenpy.lib.exception import RecordNotFoundException  # type: ignore
from zenpy.lib.generator import SearchExportResultGenerator  # type: ignore

from teamster.libraries.zendesk.resources import ZendeskResource


def build_ticket_metrics_archive(code_location, timezone, avro_schema):
    @asset(
        key=[code_location, "zendesk", "ticket_metrics_archive"],
        io_manager_key="io_manager_gcs_file",
        partitions_def=MonthlyPartitionsDefinition(
            start_date=datetime(year=2011, month=7, day=1),
            end_date=datetime(year=2023, month=6, day=30),
            timezone=timezone,
        ),
        group_name="zendesk",
        kinds={"python"},
    )
    def _asset(context: AssetExecutionContext, zendesk: ZendeskResource):
        partition_key = check.not_none(value=context.partition_key)

        partition_key_datetime = datetime.fromisoformat(partition_key)

        data_filepath = pathlib.Path("env/ticket_metrics_archive/data.avro")
        schema = parse_schema(schema=avro_schema)

        start_date = partition_key_datetime - relativedelta(seconds=1)
        end_date = partition_key_datetime + relativedelta(months=1)

        context.log.info(
            f"Searching closed tickets: updated>{start_date} updated<{end_date}"
        )
        archived_tickets = check.inst(
            zendesk._client.search_export(
                type="ticket", status="closed", updated_between=[start_date, end_date]
            ),
            SearchExportResultGenerator,
        )

        context.log.info(f"Saving results to {data_filepath}")
        data_filepath.parent.mkdir(parents=True, exist_ok=True)

        writer(
            fo=data_filepath.open("wb"),
            schema=schema,
            records=[],
            codec="snappy",
            strict_allow_default=True,
        )

        fo = data_filepath.open("a+b")

        for ticket in archived_tickets:
            ticket_id = ticket.id

            context.log.info(f"Getting metrics for ticket #{ticket_id}")
            metrics = check.inst(zendesk._client.tickets.metrics(ticket_id), BaseObject)

            try:
                writer(
                    fo=fo,
                    schema=schema,
                    records=[metrics.to_dict()],
                    codec="snappy",
                    strict_allow_default=True,
                )
            except RecordNotFoundException as e:
                context.log.exception(msg=e)
                continue

        fo.close()

        try:
            with data_filepath.open(mode="rb") as f:
                num_records = sum(block.num_records for block in block_reader(f))
        except FileNotFoundError:
            num_records = 0

        yield Output(value=data_filepath, metadata={"records": num_records})

    return _asset
