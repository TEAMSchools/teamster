from dagster import graph

from teamster.common.ops.powerschool import (
    compose_queries,
    compose_resyncs,
    compose_tables,
    filter_queries,
    get_count,
    get_data,
)


@graph
def execute_query(table_query):
    # get record count, end if 0
    count_outs = get_count(table_query=table_query)

    # get data and save file to data lake
    get_data(
        table=count_outs.table,
        projection=count_outs.projection,
        query=count_outs.query,
        n_pages=count_outs.n_pages,
    )


@graph
def run_queries():
    # parse queries from run config file (config/powerschool/query-*.yaml)
    ct_outs = compose_tables()

    # execute composed queries and filter parsed queries
    ct_outs.dynamic_tables.map(execute_query)
    fq_outs = filter_queries(ct_outs.table_queries)

    # execute composed queries, compose parsed queries & resyncs
    fq_outs.dynamic_tables.map(execute_query)
    cq_dynamic_tables = compose_queries(fq_outs.table_queries)
    cr_dynamic_tables = compose_resyncs(fq_outs.table_resyncs)

    # execute parsed queries and resyncs
    cq_dynamic_tables.map(execute_query)
    cr_dynamic_tables.map(execute_query)
