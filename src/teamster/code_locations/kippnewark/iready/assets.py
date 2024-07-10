from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.code_locations.kippnewark.iready.schema import (
    DIAGNOSTIC_AND_INSTRUCTION_SCHEMA,
    DIAGNOSTIC_RESULTS_SCHEMA,
    INSTRUCTIONAL_USAGE_DATA_SCHEMA,
    PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

ssh_resource_key = "ssh_iready"
remote_dir_regex = r"/exports/nj-kipp_nj/(?P<academic_year>\w+)"
slugify_replacements = [["%", "percent"]]
key_prefix = [CODE_LOCATION, "iready"]

subject_partitions_def = StaticPartitionsDefinition(["ela", "math"])

diagnostic_results = build_sftp_file_asset(
    asset_key=[*key_prefix, "diagnostic_results"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"diagnostic_results_(?P<subject>\w+)\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=DIAGNOSTIC_RESULTS_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": subject_partitions_def,
            "academic_year": StaticPartitionsDefinition(
                ["Current_Year", "2023", "2022", "2021", "2020"]
            ),
        }
    ),
    slugify_replacements=slugify_replacements,
)

personalized_instruction_by_lesson = build_sftp_file_asset(
    asset_key=[*key_prefix, "personalized_instruction_by_lesson"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"personalized_instruction_by_lesson_(?P<subject>\w+)\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": subject_partitions_def,
            "academic_year": StaticPartitionsDefinition(
                ["Current_Year", "2023", "2022"]
            ),
        }
    ),
    slugify_replacements=slugify_replacements,
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "750m"}, "limits": {"cpu": "750m"}}
            }
        }
    },
)

instructional_usage_data = build_sftp_file_asset(
    asset_key=[*key_prefix, "instructional_usage_data"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"instructional_usage_data_(?P<subject>\w+)\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=INSTRUCTIONAL_USAGE_DATA_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": subject_partitions_def,
            "academic_year": StaticPartitionsDefinition(
                ["Current_Year", "2023", "2022"]
            ),
        }
    ),
    slugify_replacements=slugify_replacements,
)

diagnostic_and_instruction = build_sftp_file_asset(
    asset_key=[*key_prefix, "diagnostic_and_instruction"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"diagnostic_and_instruction_(?P<subject>\w+)_ytd_window\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=DIAGNOSTIC_AND_INSTRUCTION_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": subject_partitions_def,
            "academic_year": StaticPartitionsDefinition(
                ["Current_Year", "2023", "2022", "2021"]
            ),
        }
    ),
    slugify_replacements=slugify_replacements,
)

assets = [
    diagnostic_and_instruction,
    diagnostic_results,
    instructional_usage_data,
    personalized_instruction_by_lesson,
]
