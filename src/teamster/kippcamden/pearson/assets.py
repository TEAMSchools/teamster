import pathlib

from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.pearson.schema import ASSET_SCHEMA
from teamster.core.sftp.assets import build_sftp_asset
from teamster.kippcamden import CODE_LOCATION

config_dir = pathlib.Path(__file__).parent / "config"

njgpa = build_sftp_asset(
    asset_key=[CODE_LOCATION, "pearson", "njgpa"],
    remote_dir=f"/data-team/{CODE_LOCATION}/pearson/njgpa",
    remote_file_regex="pc(?P<administration>[a-z]+)(?P<fiscal_year>\d+)_NJ-\d+_\w+GPA\w+\.csv",
    avro_schema=ASSET_SCHEMA["njgpa"],
    ssh_resource_key="ssh_couchdrop",
    partitions_def=MultiPartitionsDefinition(
        {
            "fiscal_year": StaticPartitionsDefinition(["23"]),
            "administration": StaticPartitionsDefinition(["spr", "fbk"]),
        }
    ),
)

student_list_report = build_sftp_asset(
    asset_key=[CODE_LOCATION, "pearson", "student_list_report"],
    remote_dir=f"/data-team/{CODE_LOCATION}/pearson/student_list_report",
    remote_file_regex=r"(?P<fiscal_year>\d+)/(?P<administration>[a-z]+)/StudentListReport_(?P<administration>[A-za-z]+)(?P<fiscal_year>\d+) - \d+-\d+-\d+T\d+_\d+_\d+\.\d++\d+.csv",
    avro_schema=ASSET_SCHEMA["student_list_report"],
    ssh_resource_key="ssh_couchdrop",
    partitions_def=MultiPartitionsDefinition(
        {
            "fiscal_year": StaticPartitionsDefinition(["2023", "2022"]),
            "administration": StaticPartitionsDefinition(["Spring", "Fall"]),
        }
    ),
)

static_partition_assets = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "pearson", a["asset_name"]],
        avro_schema=ASSET_SCHEMA[a["asset_name"]],
        ssh_resource_key="ssh_couchdrop",
        partitions_def=StaticPartitionsDefinition(a["partition_keys"]),
        **a,
    )
    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
]

assets = [
    njgpa,
    student_list_report,
    *static_partition_assets,
]
