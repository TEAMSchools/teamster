import pandas
from dagster import (
    AssetExecutionContext,
    AssetKey,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
)
from dagster_gcp import BigQueryResource
from dagster_shared import check

from teamster.code_locations.kipptaf import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kipptaf.performance_management.schema import (
    OBSERVATION_DETAILS_SCHEMA,
    OUTLIER_DETECTION_SCHEMA,
)
from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.performance_management.outlier_detection import (
    score_partition,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset


@asset(
    key=[CODE_LOCATION, "performance_management", "outlier_detection"],
    deps=[AssetKey(["kipptaf", "extracts", "rpt_python__manager_pm_averages"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="performance_management",
    partitions_def=MultiPartitionsDefinition(
        {
            "academic_year": StaticPartitionsDefinition(
                [str(year) for year in range(2023, CURRENT_FISCAL_YEAR.fiscal_year)]
            ),
            "term": StaticPartitionsDefinition(["PM1", "PM2", "PM3"]),
        }
    ),
    output_required=False,
    check_specs=[
        build_check_spec_avro_schema_valid(
            [CODE_LOCATION, "performance_management", "outlier_detection"]
        )
    ],
)
def outlier_detection(context: AssetExecutionContext, db_bigquery: BigQueryResource):
    partition_key = check.inst(context.partition_key, MultiPartitionKey)

    # load data from extract view
    with db_bigquery.get_client() as bq:
        bq_client = bq

    query = bq.query(
        query="select * from kipptaf_extracts.rpt_python__manager_pm_averages",
        project=bq_client.project,
    )

    df: pandas.DataFrame = query.to_dataframe()

    data = score_partition(
        df=df,
        academic_year=int(partition_key.keys_by_dimension["academic_year"]),
        form_term=partition_key.keys_by_dimension["term"],
    )

    yield Output(
        value=(data, OUTLIER_DETECTION_SCHEMA), metadata={"records": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=OUTLIER_DETECTION_SCHEMA
    )


observation_details = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "performance_management", "observation_details"],
    remote_dir_regex=(
        r"/data-team/kipptaf/performance-management/observation-details/"
        r"(?P<academic_year>\d+)/(?P<term>PM\d)"
    ),
    remote_file_regex=r"[\w-]+\.csv",
    avro_schema=OBSERVATION_DETAILS_SCHEMA,
    ssh_resource_key="ssh_couchdrop",
    partitions_def=MultiPartitionsDefinition(
        {
            "academic_year": StaticPartitionsDefinition(
                ["2018", "2019", "2020", "2021", "2022", "2023"]
            ),
            "term": StaticPartitionsDefinition(["PM1", "PM2", "PM3"]),
        }
    ),
)

assets = [
    observation_details,
    outlier_detection,
]
