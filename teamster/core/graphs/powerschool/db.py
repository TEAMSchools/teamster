from dagster import graph

from teamster.core.ops.db import compose_queries, extract


@graph
def execute_query(dynamic_query):
    # trunk-ignore(flake8/F841)
    data = extract(dynamic_query=dynamic_query)


@graph
def run_queries():
    # parse queries from run config file
    dynamic_query = compose_queries()

    # execute composed queries and transform to configured file type
    dynamic_query.map(execute_query)


@graph
def resync():
    # full
    dynamic_query = compose_queries()
    dynamic_query.map(execute_query)

    # log
    dynamic_query = compose_queries()
    dynamic_query.map(execute_query)

    # attendance
    dynamic_query = compose_queries()
    dynamic_query.map(execute_query)

    # storedgrades
    dynamic_query = compose_queries()
    dynamic_query.map(execute_query)

    # pgfinalgrades
    dynamic_query = compose_queries()
    dynamic_query.map(execute_query)

    # assignmentscore
    dynamic_query = compose_queries()
    dynamic_query.map(execute_query)
