import json

from dagster import AssetExecutionContext
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets


def build_dbt_assets(
    manifest,
    dagster_dbt_translator: DagsterDbtTranslator,
    select: str = "fqn:*",
    exclude: str | None = None,
    partitions_def=None,
    name: str | None = None,
    op_tags: dict[str, object] | None = None,
):
    sources = manifest["sources"]

    @dbt_assets(
        manifest=manifest,
        select=select,
        exclude=exclude,
        name=name,
        partitions_def=partitions_def,
        dagster_dbt_translator=dagster_dbt_translator,
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        # get upstream nodes for asset selection
        selection_depends_on_nodes = [
            node
            for node_props in manifest["nodes"].values()
            for node in node_props["depends_on"]["nodes"]
            if dagster_dbt_translator.get_asset_key(node_props)
            in context.selected_asset_keys
        ]

        # filter upstream nodes for external sources
        external_sources = [
            sources[node]
            for node in selection_depends_on_nodes
            if sources.get(node, {}).get("external")
        ]

        if external_sources:
            # stage external sources
            select = " ".join(
                {f"{s['source_name']}.{s['name']}" for s in external_sources}
            )

            stage_external_sources = dbt_cli.cli(
                args=[
                    "run-operation",
                    "stage_external_sources",
                    "--args",
                    json.dumps({"select": select}),
                    "--vars",
                    json.dumps({"ext_full_refresh": "true"}),
                ],
                manifest=manifest,
                dagster_dbt_translator=dagster_dbt_translator,
            )

            for event in stage_external_sources.stream_raw_events():
                context.log.info(msg=event)

            # refresh_external_metadata_cache for biglake tables
            relation_names = {
                s["relation_name"]
                for s in external_sources
                if s["external"]["options"].get("connection_name") is not None
            }

            if relation_names:
                refresh_external_metadata_cache = dbt_cli.cli(
                    args=[
                        "run-operation",
                        "refresh_external_metadata_cache",
                        "--args",
                        json.dumps({"relation_names": list(relation_names)}),
                    ],
                    manifest=manifest,
                    dagster_dbt_translator=dagster_dbt_translator,
                )

                for event in refresh_external_metadata_cache.stream_raw_events():
                    context.log.info(msg=event)

        # build models
        dbt_build = dbt_cli.cli(args=["build"], context=context)

        yield from dbt_build.stream().fetch_column_metadata(with_column_lineage=False)

    return _assets
