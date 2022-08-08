from dagster import graph

from teamster.common.ops.datagun import (
    compose_queries,
    extract,
    load_destination,
    transform,
)


@graph
def execute_query(dynamic_query):
    data, file_config, dest_config = extract(dynamic_query=dynamic_query)

    transformed = transform(data=data, file_config=file_config, dest_config=dest_config)

    return transformed


@graph
def run_queries():
    # parse queries from run config file (./teamster/local/config/datagun/query-*.yaml)
    dynamic_query = compose_queries()

    # execute composed queries and transform to configured file type
    transformed = dynamic_query.map(execute_query)

    transformed.map(load_destination)
