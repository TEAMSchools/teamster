from dagster import file_relative_path
from dagster_embedded_elt.sling import (
    DagsterSlingTranslator,
    SlingResource,
    sling_assets,
)

replication_config = file_relative_path(
    dunderfile=__file__, relative_path="replication.yaml"
)


@sling_assets(replication_config=replication_config)
def illuminate_table_assets(context, sling: SlingResource):
    yield from sling.replicate(
        replication_config=replication_config,
        dagster_sling_translator=DagsterSlingTranslator(),
        debug=True,
    )

    for row in sling.stream_raw_logs():
        context.log.info(row)


_all = [
    illuminate_table_assets,
]
