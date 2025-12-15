from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kipppaterson import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kipppaterson.pearson.schema import (
    NJSLA_SCHEMA,
    STUDENT_LIST_REPORT_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

ssh_resource_key = "ssh_couchdrop"
remote_dir_regex_prefix = f"/data-team/{CODE_LOCATION}/pearson"
key_prefix = [CODE_LOCATION, "pearson"]

student_list_report = build_sftp_file_asset(
    asset_key=[*key_prefix, "student_list_report"],
    remote_dir_regex=(
        rf"{remote_dir_regex_prefix}/student_list_report/(?P<test_type>[a-z]+)"
    ),
    remote_file_regex=(
        r"StudentListReport_(?P<administration_fiscal_year>[A-Za-z]+\d+)"
        r"(_\d+_|\s-\s)\d+-\d+-\d+(T\w+\.\d+\+\d+)?\.csv"
    ),
    avro_schema=STUDENT_LIST_REPORT_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=MultiPartitionsDefinition(
        {
            "test_type": StaticPartitionsDefinition(["njsla"]),
            "administration_fiscal_year": StaticPartitionsDefinition(
                [
                    f"Spring{year}"
                    for year in range(2025, CURRENT_FISCAL_YEAR.fiscal_year + 1)
                ]
            ),
        }
    ),
)

njsla = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla",
    remote_file_regex=r"pcspr(?P<fiscal_year>\d+)_NJ-\d+(-\d+)?_\w+\.csv",
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=StaticPartitionsDefinition(
        [str(year)[-2:] for year in range(2024, CURRENT_FISCAL_YEAR.fiscal_year + 1)]
    ),
)

njsla_science = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla_science"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla_science",
    remote_file_regex=r"njs(?P<fiscal_year>\d+)_NJ-\d+_\w+\.csv",
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=StaticPartitionsDefinition(
        [str(year)[-2:] for year in range(2024, CURRENT_FISCAL_YEAR.fiscal_year + 1)]
    ),
)

assets = [
    njsla_science,
    njsla,
    student_list_report,
]
