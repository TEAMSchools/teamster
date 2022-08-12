from dagster import graph

from teamster.common.ops.db import (
    compose_queries,
    extract,
    start_ssh_tunnel,
    stop_ssh_tunnel,
    transform,
)


@graph
def execute_query(dynamic_query):
    data, file_config, dest_config = extract(dynamic_query=dynamic_query)

    transform(data=data, file_config=file_config, dest_config=dest_config)


@graph
def run_queries():
    # parse queries from run config file
    dynamic_query = compose_queries()

    ssh_tunnel = start_ssh_tunnel()

    # execute composed queries and transform to configured file type
    dynamic_query.map(execute_query)

    stop_ssh_tunnel(ssh_tunnel=ssh_tunnel)
