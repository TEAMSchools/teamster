import json

from dagster import AssetExecutionContext, Failure, Output, asset
from dagster_dbt.asset_decorator import dbt_assets
from dagster_dbt.cli import DbtCli
from dagster_gcp import BigQueryResource


def build_dbt_assets(manifest, select="fqn:*", exclude=None):
    @dbt_assets(manifest=manifest)
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCli):
        dbt_build = dbt_cli.cli(args=["build"], manifest=manifest, context=context)

        yield from dbt_build.stream()

    return _assets


def build_external_source_asset(
    code_location,
    name,
    dbt_package_name,
    upstream_asset_key,
    group_name,
    manifest,
):
    @asset(
        key=[code_location, dbt_package_name, name],
        non_argument_deps=[upstream_asset_key],
        compute_kind="dbt",
        group_name=group_name,
    )
    def _asset(
        context: AssetExecutionContext, dbt_cli: DbtCli, db_bigquery: BigQueryResource
    ):
        dataset_name = f"{code_location}_{dbt_package_name}"

        # create BigQuery dataset, if not exists
        context.log.info(f"Creating dataset {dataset_name}")
        with db_bigquery.get_client() as bq:
            bq.create_dataset(dataset=dataset_name, exists_ok=True)

        # stage_external_sources
        dbt_run_operation = dbt_cli.cli(
            args=[
                "run-operation",
                "stage_external_sources",
                "--args",
                json.dumps({"select": f"{dbt_package_name}.{name}"}),
                "--vars",
                json.dumps({"ext_full_refresh": True}),
            ],
            manifest=manifest,
            context=context,
        )

        for event in dbt_run_operation.stream_raw_events():
            context.log.info(event)

        if dbt_run_operation.is_successful():
            return Output(value=True)
        else:
            raise Failure()

    return _asset
