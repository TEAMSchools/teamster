from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippnewark.pearson.schema import (
    NJGPA_SCHEMA,
    NJSLA_SCHEMA,
    NJSLA_SCIENCE_SCHEMA,
    PARCC_SCHEMA,
    STUDENT_LIST_REPORT_SCHEMA,
    STUDENT_TEST_UPDATE_SCHEMA,
)
from teamster.libraries.sftp.assets import (
    build_sftp_file_asset,
    build_sftp_folder_asset,
)

ssh_resource_key = "ssh_couchdrop"
remote_dir_regex_prefix = f"/data-team/{CODE_LOCATION}/pearson"
key_prefix = [CODE_LOCATION, "pearson"]

njgpa = build_sftp_file_asset(
    asset_key=[*key_prefix, "njgpa"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njgpa",
    remote_file_regex=(
        r"pc(?P<administration>[a-z]+)"
        r"(?P<fiscal_year>\d+)_NJ-\d+(-\d+)?_\w+GPA\w+\.csv"
    ),
    avro_schema=NJGPA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=MultiPartitionsDefinition(
        {
            "fiscal_year": StaticPartitionsDefinition(
                [
                    str(year)[-2:]
                    for year in range(2022, CURRENT_FISCAL_YEAR.fiscal_year + 1)
                ]
            ),
            "administration": StaticPartitionsDefinition(["spr", "fbk"]),
        }
    ),
)

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
            "test_type": StaticPartitionsDefinition(["njsla", "njgpa"]),
            "administration_fiscal_year": StaticPartitionsDefinition(
                [
                    f"Spring{year}"
                    for year in range(2022, CURRENT_FISCAL_YEAR.fiscal_year + 1)
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
        [str(year)[-2:] for year in range(2019, CURRENT_FISCAL_YEAR.fiscal_year + 1)]
    ),
)

njsla_science = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla_science"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla_science",
    remote_file_regex=r"njs(?P<fiscal_year>\d+)_NJ-\d+_\w+\.csv",
    avro_schema=NJSLA_SCIENCE_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=StaticPartitionsDefinition(
        [str(year)[-2:] for year in range(2022, CURRENT_FISCAL_YEAR.fiscal_year + 1)]
    ),
)

parcc = build_sftp_file_asset(
    asset_key=[*key_prefix, "parcc"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/parcc",
    remote_file_regex=r"PC_pcspr(?P<fiscal_year>\d+)_NJ-\d+(-\d+)?_\w+\.csv",
    avro_schema=PARCC_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=StaticPartitionsDefinition(["16", "17", "18"]),
)

student_test_update = build_sftp_folder_asset(
    asset_key=[*key_prefix, "student_test_update"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/student_test_update",
    remote_file_regex=(
        r"Student\sTest\sUpdate\sExport\s\d+-\d+-\d+T\d+_\d+_\d+\.\d+\+\d+"
    ),
    avro_schema=STUDENT_TEST_UPDATE_SCHEMA,
    file_dtype=str,
    ssh_resource_key=ssh_resource_key,
)

assets = [
    njgpa,
    njsla_science,
    njsla,
    parcc,
    student_list_report,
    student_test_update,
]
