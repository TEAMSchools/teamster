import pathlib

import pendulum
from dagster import (
    AssetExecutionContext,
    MonthlyPartitionsDefinition,
    Output,
    _check,
    asset,
)
from fastavro import block_reader, parse_schema, writer
from pendulum.datetime import DateTime
from zenpy.lib.api_objects import BaseObject
from zenpy.lib.exception import RecordNotFoundException
from zenpy.lib.generator import SearchExportResultGenerator

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.zendesk.schema import TICKET_METRIC_SCHEMA
from teamster.libraries.zendesk.resources import ZendeskResource


@asset(
    key=[CODE_LOCATION, "zendesk", "ticket_metrics_archive"],
    io_manager_key="io_manager_gcs_file",
    partitions_def=MonthlyPartitionsDefinition(
        start_date=pendulum.datetime(2011, 7, 1),
        end_date=pendulum.datetime(2023, 6, 30),
        timezone=LOCAL_TIMEZONE.name,
    ),
    group_name="zendesk",
    compute_kind="python",
)
def ticket_metrics_archive(context: AssetExecutionContext, zendesk: ZendeskResource):
    partition_key = _check.not_none(value=context.partition_key)

    partition_key_datetime = _check.inst(pendulum.parse(text=partition_key), DateTime)

    data_filepath = pathlib.Path("env/ticket_metrics_archive/data.avro")
    schema = parse_schema(schema=TICKET_METRIC_SCHEMA)

    start_date = partition_key_datetime.subtract(seconds=1)
    end_date = partition_key_datetime.add(months=1)

    context.log.info(
        f"Searching closed tickets: updated>{start_date} updated<{end_date}"
    )
    archived_tickets = _check.inst(
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

    try:
        for ticket in archived_tickets:
            ticket_id = ticket.id

            context.log.info(f"Getting metrics for ticket #{ticket_id}")
            metrics = _check.inst(
                zendesk._client.tickets.metrics(ticket_id), BaseObject
            )

            try:
                writer(
                    fo=fo,
                    schema=schema,
                    records=[metrics.to_dict()],
                    codec="snappy",
                    strict_allow_default=True,
                )
            except RecordNotFoundException as e:
                context.log.exception(e)
                pass

    except IndexError as e:
        context.log.exception(e)
        pass

    fo.close()

    try:
        with data_filepath.open(mode="rb") as f:
            num_records = sum(block.num_records for block in block_reader(f))
    except FileNotFoundError:
        num_records = 0

    yield Output(value=data_filepath, metadata={"records": num_records})


assets = [
    ticket_metrics_archive,
]
