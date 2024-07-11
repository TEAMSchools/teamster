from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.code_locations.kippnewark.pearson.schema import (
    NJGPA_SCHEMA,
    NJSLA_SCHEMA,
    NJSLA_SCIENCE_SCHEMA,
    PARCC_SCHEMA,
    STUDENT_LIST_REPORT_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

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
            "fiscal_year": StaticPartitionsDefinition(["22", "23", "24"]),
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
        r"StudentListReport_(?P<administration_fiscal_year>[A-za-z]+\d+)"
        r"(_\d+_|\s-\s)\d+-\d+-\d+(T\w+\.\d+\+\d+)?\.csv"
    ),
    avro_schema=STUDENT_LIST_REPORT_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=MultiPartitionsDefinition(
        {
            "test_type": StaticPartitionsDefinition(["njsla", "njgpa"]),
            "administration_fiscal_year": StaticPartitionsDefinition(
                ["Spring2024", "Spring2023", "Spring2022"]
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
    partitions_def=StaticPartitionsDefinition(["19", "22", "23"]),
)

njsla_science = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla_science"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla_science",
    remote_file_regex=r"njs(?P<fiscal_year>\d+)_NJ-\d+_\w+\.csv",
    avro_schema=NJSLA_SCIENCE_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=StaticPartitionsDefinition(["22", "23"]),
)

parcc = build_sftp_file_asset(
    asset_key=[*key_prefix, "parcc"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/parcc",
    remote_file_regex=r"PC_pcspr(?P<fiscal_year>\d+)_NJ-\d+(-\d+)?_\w+\.csv",
    avro_schema=PARCC_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=StaticPartitionsDefinition(["16", "17", "18"]),
)

assets = [
    njgpa,
    njsla_science,
    njsla,
    parcc,
    student_list_report,
]
