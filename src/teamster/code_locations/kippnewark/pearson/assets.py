import pathlib

from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.code_locations.kippnewark.pearson.schema import ASSET_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_asset

config_dir = pathlib.Path(__file__).parent / "config"

njgpa = build_sftp_asset(
    asset_key=[CODE_LOCATION, "pearson", "njgpa"],
    remote_dir=f"/data-team/{CODE_LOCATION}/pearson/njgpa",
    remote_file_regex=r"pc(?P<administration>[a-z])(?P<fiscal_year>\d+)_NJ-\d+_\w+GPA\w+\.csv",
    avro_schema=ASSET_SCHEMA["njgpa"],
    ssh_resource_key="ssh_couchdrop",
    partitions_def=MultiPartitionsDefinition(
        {
            "fiscal_year": StaticPartitionsDefinition(["22", "23"]),
            "administration": StaticPartitionsDefinition(["spr", "fbk"]),
        }
    ),
)

student_list_report = build_sftp_asset(
    asset_key=[CODE_LOCATION, "pearson", "student_list_report"],
    remote_dir=f"/data-team/{CODE_LOCATION}/pearson/student_list_report",
    remote_file_regex=(
        r"(?P<test_type>[a-z]+)\/StudentListReport_"
        r"(?P<administration_fiscal_year>[A-za-z]+\d+) - "
        r"\d+-\d+-\d+T\d+_\d+_\d+\.\d+\+\d+\.csv"
    ),
    avro_schema=ASSET_SCHEMA["student_list_report"],
    ssh_resource_key="ssh_couchdrop",
    partitions_def=MultiPartitionsDefinition(
        {
            "test_type": StaticPartitionsDefinition(["njsla", "njgpa"]),
            "administration_fiscal_year": StaticPartitionsDefinition(
                ["Spring2023", "Spring2022"]
            ),
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
