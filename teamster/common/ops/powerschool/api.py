import gzip
import json
import math
import re

from dagster import (
    Any,
    Backoff,
    Bool,
    DynamicOut,
    DynamicOutput,
    Field,
    In,
    Int,
    Jitter,
    List,
    Nothing,
    Optional,
    Out,
    Output,
    RetryPolicy,
    RetryRequested,
    String,
    Tuple,
    op,
)
from powerschool.utils import (
    generate_historical_queries,
    get_constraint_rules,
    get_constraint_values,
    get_query_expression,
    transform_year_id,
)
from requests.exceptions import HTTPError

from teamster.common.config.powerschool import COMPOSE_API_QUERIES_CONFIG
from teamster.common.utils import TODAY, get_last_schedule_run, time_limit


@op(
    ins={"table_resyncs": In(dagster_type=List[Tuple])},
    out={"dynamic_tables": DynamicOut(dagster_type=Tuple, is_required=False)},
    config_schema={
        "step_size": Field(Int, is_required=False, default_value=30000),
        "force": Field(Bool, is_required=False, default_value=False),
    },
    tags={"dagster/priority": 1},
)
def compose_resyncs(context, table_resyncs):
    for tr in table_resyncs:
        year_id, table, projection, selector, max_value = tr

        context.log.info(f"Generating historical queries for {table.name}.")

        if not max_value and selector[-2:] == "id":
            max_value = int(
                table.query(
                    projection=selector,
                    sort=selector,
                    sortdescending="true",
                    pagesize=1,
                    page=1,
                )[0][selector]
            )
            place_value = 10 ** (len(str(max_value)) - 1)
            max_val_ceil = math.ceil(max_value / place_value) * place_value
            max_value = max_val_ceil
        elif not max_value:
            max_value = transform_year_id(year_id, selector)
        context.log.debug(f"max_value:\t{max_value}")
        constraint_rules = get_constraint_rules(
            selector, year_id=year_id, is_historical=True
        )

        historical_queries = generate_historical_queries(
            selector=selector,
            start_value=max_value,
            stop_value=constraint_rules["stop_value"],
            step_size=context.op_config["step_size"],
        )
        historical_queries.reverse()

        for i, hq in enumerate(historical_queries):
            yield DynamicOutput(
                value=(table, projection, hq, True),
                output_name="dynamic_tables",
                mapping_key=f"{re.sub(r'[^A-Za-z0-9]', '_', table.name)}_h_{i}",
            )


@op(
    ins={"table_queries": In(dagster_type=List[Tuple])},
    out={"dynamic_tables": DynamicOut(dagster_type=Tuple, is_required=False)},
    tags={"dagster/priority": 2},
)
def compose_queries(context, table_queries):
    for ftq in table_queries:
        year_id, table, mapping_key, projection, selector, value = ftq

        constraint_rules = get_constraint_rules(selector=selector, year_id=year_id)

        constraint_values = get_constraint_values(
            selector=selector,
            value=value,
            step_size=constraint_rules["step_size"],
        )

        composed_query = get_query_expression(selector=selector, **constraint_values)

        yield DynamicOutput(
            value=(table, projection, composed_query, False),
            output_name="dynamic_tables",
            mapping_key=mapping_key,
        )


@op(
    ins={"table_queries": In(dagster_type=List[Tuple])},
    out={
        "dynamic_tables": DynamicOut(dagster_type=Tuple, is_required=False),
        "table_queries": Out(dagster_type=List[Tuple], is_required=False),
        "table_resyncs": Out(dagster_type=List[Tuple], is_required=False),
    },
    tags={"dagster/priority": 3},
)
def filter_queries(context, table_queries):
    table_queries_filtered = []
    table_resyncs = []

    for tbl in table_queries:
        year_id, table, projection, queries = tbl

        for i, query in enumerate(queries):
            mapping_key = f"{re.sub(r'[^A-Za-z0-9]', '_', table.name)}_q_{i}"

            projection = query.get("projection", projection)
            q = query.get("q")

            if isinstance(q, str):
                yield DynamicOutput(
                    value=(table, projection, q, False),
                    output_name="dynamic_tables",
                    mapping_key=mapping_key,
                )
            else:
                selector = q["selector"]
                max_value = q.get("max_value")
                value = q.get("value", transform_year_id(year_id, selector))

                if value == "today":
                    value = TODAY.date().isoformat()

                if value == "resync":
                    table_resyncs.append(
                        (year_id, table, projection, selector, max_value)
                    )
                else:
                    table_queries_filtered.append(
                        (year_id, table, mapping_key, projection, selector, value)
                    )

    if table_queries_filtered:
        yield Output(value=table_queries_filtered, output_name="table_queries")

    if table_resyncs:
        yield Output(value=table_resyncs, output_name="table_resyncs")


@op(
    config_schema=COMPOSE_API_QUERIES_CONFIG,
    out={
        "dynamic_tables": DynamicOut(dagster_type=Tuple, is_required=False),
        "table_queries": Out(dagster_type=List[Tuple], is_required=False),
    },
    required_resource_keys={"powerschool"},
    tags={"dagster/priority": 4},
)
def compose_tables(context):
    tables = context.op_config["tables"]
    year_id = context.op_config["year_id"]

    table_queries = []
    for i, tbl in enumerate(tables):
        table = context.resources.powerschool.get_schema_table(tbl["name"])
        projection = tbl.get("projection")
        queries = [fq for fq in tbl.get("queries", {}) if fq.get("q")]

        if queries:
            table_queries.append((year_id, table, projection, queries))
        else:
            yield DynamicOutput(
                value=(table, projection, None, False),
                output_name="dynamic_tables",
                mapping_key=f"{re.sub(r'[^A-Za-z0-9]', '_', table.name)}_t_{i}",
            )

    if table_queries:
        yield Output(value=table_queries, output_name="table_queries")


def table_count(context, table, query):
    try:
        return table.count(q=query)
    except Exception as e:
        context.log.error(e)
        raise e


def time_limit_count(context, table, query, count_type):
    if count_type == "incremental":
        last_run_datetime = get_last_schedule_run(context)
        if last_run_datetime:
            last_run_date = last_run_datetime.date().isoformat()
        else:
            # proceed to original query count
            context.log.info("No Schedule - Skipping `transaction_date` count.")
            return 1

        context.log.info(
            f"Searching for matching records updated since {last_run_date}."
        )

        query = ";".join(
            [
                f"transaction_date=ge={last_run_date}",
                str(query or ""),
            ]
        )

    with time_limit(context.op_config["query_timeout"]):
        try:
            return table_count(context=context, table=table, query=query)
        except HTTPError as e:
            if str(e) == '{"message":"Invalid field transaction_date"}':
                # proceed to original query count
                context.log.warning("Skipping transaction_date count.")
                return 1
            else:
                raise e


@op(
    ins={"table_query": In(dagster_type=Tuple)},
    out={
        "table": Out(dagster_type=Any, is_required=False),
        "projection": Out(dagster_type=Optional[String], is_required=False),
        "query": Out(dagster_type=Optional[String], is_required=False),
        "n_pages": Out(dagster_type=Int, is_required=False),
        "no_count": Out(dagster_type=Nothing, is_required=False),
    },
    retry_policy=RetryPolicy(
        max_retries=5, delay=30, backoff=Backoff.EXPONENTIAL, jitter=Jitter.PLUS_MINUS
    ),
    config_schema={
        "query_timeout": Field(Int, is_required=False, default_value=30),
        "skip_incremental": Field(Bool, is_required=False),
    },
    tags={"dagster/priority": 5},
)
def get_count(context, table_query):
    table, projection, query, is_resync = table_query
    context.log.info(
        f"table:\t\t{table.name}\nprojection:\t{projection}\nq:\t\t{query}"
    )

    if is_resync or context.op_config.get("skip_incremental"):
        context.log.info("Skipping `transaction_date` count.")
        updated_count = 1
    else:
        try:
            # count query records updated since last run
            updated_count = time_limit_count(
                context=context, table=table, query=query, count_type="incremental"
            )
        except Exception as e:
            raise RetryRequested(
                max_retries=context.op_def.retry_policy.max_retries,
                seconds_to_wait=context.op_def.retry_policy.delay,
            ) from e

    if updated_count > 0:
        try:
            # count all records in query
            query_count = time_limit_count(
                context=context, table=table, query=query, count_type="query"
            )
        except Exception as e:
            raise RetryRequested(
                max_retries=context.op_def.retry_policy.max_retries,
                seconds_to_wait=context.op_def.retry_policy.delay,
            ) from e
    else:
        context.log.info("No record updates since last run. Skipping.")
        return Output(value=None, output_name="no_count")

    context.log.info(f"count:\t{query_count}")
    if query_count > 0:
        n_pages = math.ceil(
            query_count / table.client.metadata.schema_table_query_max_page_size
        )
        context.log.info(f"total pages:\t{n_pages}")

        yield Output(value=table, output_name="table")
        yield Output(value=query, output_name="query")
        yield Output(value=projection, output_name="projection")
        yield Output(value=n_pages, output_name="n_pages")
    else:
        return Output(value=None, output_name="no_count")


def table_query(context, table, query, projection, page):
    try:
        return table.query(q=query, projection=projection, page=page)
    except Exception as e:
        context.log.error(e)
        raise e


def time_limit_query(context, table, query, projection, page, retry=False):
    with time_limit(context.op_config["query_timeout"]):
        try:
            return table_query(
                context=context,
                table=table,
                query=query,
                projection=projection,
                page=page,
            )
        except Exception as e:
            if retry:
                raise e
            else:
                # retry page before retrying entire Op
                return time_limit_query(
                    context=context,
                    table=table,
                    query=query,
                    projection=projection,
                    page=page,
                    retry=True,
                )


@op(
    ins={
        "table": In(dagster_type=Any),
        "projection": In(dagster_type=Optional[String]),
        "query": In(dagster_type=Optional[String]),
        "n_pages": In(dagster_type=Int),
    },
    out={"gcs_file_handles": Out(dagster_type=List)},
    required_resource_keys={"file_manager"},
    retry_policy=RetryPolicy(
        max_retries=5, delay=30, backoff=Backoff.EXPONENTIAL, jitter=Jitter.PLUS_MINUS
    ),
    config_schema={"query_timeout": Field(Int, is_required=False, default_value=30)},
    tags={"dagster/priority": 6},
)
def get_data(context, table, projection, query, n_pages):
    context.log.debug(
        f"table:\t\t{table.name}\nprojection:\t{projection}\nq:\t\t{query}"
    )

    file_stem = "_".join(filter(None, [table.name, str(query or "")]))

    gcs_file_handles = []
    for p in range(n_pages):
        file_key = f"{table.name}/{file_stem}_p_{p}.json.gz"

        if context.retry_number > 0 and context.resources.file_manager._has_object(
            key=file_key
        ):
            context.log.debug("File already exists from previous try. Skipping.")
        else:
            context.log.debug(f"page:\t{(p + 1)}/{n_pages}")

            try:
                data = time_limit_query(
                    context=context,
                    table=table,
                    query=query,
                    projection=projection,
                    page=(p + 1),
                )
            except Exception as e:
                raise RetryRequested(
                    max_retries=context.op_def.retry_policy.max_retries,
                    seconds_to_wait=context.op_def.retry_policy.delay,
                ) from e

            gcs_file_handles.append(
                context.resources.file_manager.upload_from_string(
                    obj=gzip.compress(json.dumps(data).encode("utf-8")),
                    file_key=file_key,
                )
            )

    return Output(value=gcs_file_handles, output_name="gcs_file_handles")
