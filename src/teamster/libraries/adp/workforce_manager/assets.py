import time
from io import StringIO

from dagster import (
    AssetsDefinition,
    AutoMaterializePolicy,
    DailyPartitionsDefinition,
    DynamicPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    StaticPartitionsDefinition,
    _check,
    asset,
)
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.libraries.adp.workforce_manager.resources import (
    AdpWorkforceManagerResource,
)
from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)


def build_adp_wfm_asset(
    asset_key,
    report_name,
    hyperfind,
    symbolic_ids,
    schema,
    date_partitions_def: DailyPartitionsDefinition | DynamicPartitionsDefinition,
) -> AssetsDefinition:
    @asset(
        key=asset_key,
        metadata={"hyperfind": hyperfind, "report_name": report_name},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=MultiPartitionsDefinition(
            {
                "symbolic_id": StaticPartitionsDefinition(symbolic_ids),
                "date": date_partitions_def,
            }
        ),
        group_name="adp_workforce_manager",
        auto_materialize_policy=AutoMaterializePolicy.eager(),
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: OpExecutionContext, adp_wfm: AdpWorkforceManagerResource):
        asset = context.assets_def
        partition_key = _check.inst(context.partition_key, MultiPartitionKey)

        symbolic_id = partition_key.keys_by_dimension["symbolic_id"]

        symbolic_period_response = _check.not_none(
            adp_wfm.get(endpoint="v1/commons/symbolicperiod")
        )

        symbolic_period_record = [
            sp
            for sp in symbolic_period_response.json()
            if sp["symbolicId"] == symbolic_id
        ][0]

        hyperfind_response = _check.not_none(
            adp_wfm.get(endpoint="v1/commons/hyperfind")
        )

        hyperfind_record = [
            hq
            for hq in hyperfind_response.json()["hyperfindQueries"]
            if hq["name"] == asset.metadata_by_key[asset.key]["hyperfind"]
        ][0]

        context.log.info(
            f"Executing {report_name}:\n{symbolic_period_record}\n{hyperfind_record}"
        )

        report_execution_response = _check.not_none(
            adp_wfm.post(
                endpoint=f"v1/platform/reports/{report_name}/execute",
                json={
                    "parameters": [
                        {
                            "name": "DataSource",
                            "value": {"hyperfind": hyperfind_record},
                        },
                        {
                            "name": "DateRange",
                            "value": {"symbolicPeriod": symbolic_period_record},
                        },
                        {
                            "name": "Output Format",
                            "value": {"key": "csv", "title": "CSV"},
                        },  # undocumented: where does this come from?
                    ]
                },
            )
        )

        report_execution_response_json = report_execution_response.json()

        context.log.info(report_execution_response_json)
        report_execution_id = report_execution_response_json["id"]

        while True:
            report_executions_response = _check.not_none(
                adp_wfm.get(endpoint="v1/platform/report_executions")
            )

            report_execution_record = [
                rex
                for rex in report_executions_response.json()
                if rex["id"] == report_execution_id
            ][0]

            context.log.info(report_execution_record)

            if report_execution_record["status"]["qualifier"] == "Completed":
                context.log.info(f"Downloading {report_name}")

                file_response = _check.not_none(
                    adp_wfm.get(
                        endpoint=(
                            f"v1/platform/report_executions/{report_execution_id}/file"
                        )
                    )
                )

                break

            time.sleep(5)

        df = read_csv(filepath_or_buffer=StringIO(file_response.text), low_memory=False)

        df.replace({nan: None}, inplace=True)
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        row_count = df.shape[0]

        records = df.to_dict(orient="records")

        yield Output(value=(records, schema), metadata={"records": row_count})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
