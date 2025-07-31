from teamster.code_locations.kippnewark import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippnewark.iready.schema import (
    DIAGNOSTIC_AND_INSTRUCTION_SCHEMA,
    DIAGNOSTIC_RESULTS_SCHEMA,
    INSTRUCTION_BY_LESSON_SCHEMA,
    INSTRUCTIONAL_USAGE_DATA_SCHEMA,
    PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA,
)
from teamster.libraries.iready.assets import build_iready_sftp_asset

region_subfolder = "nj-kipp_nj"
key_prefix = [CODE_LOCATION, "iready"]

diagnostic_results = build_iready_sftp_asset(
    asset_key=[*key_prefix, "diagnostic_results"],
    region_subfolder=region_subfolder,
    remote_file_regex=r"diagnostic_results_(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv",
    avro_schema=DIAGNOSTIC_RESULTS_SCHEMA,
    start_fiscal_year=2021,
    end_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year,
)


instructional_usage_data = build_iready_sftp_asset(
    asset_key=[*key_prefix, "instructional_usage_data"],
    region_subfolder=region_subfolder,
    remote_file_regex=(
        r"instructional_usage_data_(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv"
    ),
    avro_schema=INSTRUCTIONAL_USAGE_DATA_SCHEMA,
    start_fiscal_year=2023,
    end_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year,
)

instruction_by_lesson = build_iready_sftp_asset(
    asset_key=[*key_prefix, "personalized_instruction_by_lesson"],
    region_subfolder=region_subfolder,
    remote_file_regex=(
        r"(personalized|iready)_instruction_by_lesson_"
        r"(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv"
    ),
    avro_schema=PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA,
    start_fiscal_year=2023,
    end_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year,
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "250m"}, "limits": {"cpu": "1000m"}}
            }
        }
    },
)

instruction_by_lesson_pro = build_iready_sftp_asset(
    asset_key=[*key_prefix, "instruction_by_lesson"],
    region_subfolder=region_subfolder,
    remote_file_regex=(
        r"iready_pro_instruction_by_lesson_(?P<subject>ela|math)_CONFIDENTIAL\.csv"
    ),
    avro_schema=INSTRUCTION_BY_LESSON_SCHEMA,
    start_fiscal_year=2025,
    end_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year,
)

diagnostic_and_instruction = build_iready_sftp_asset(
    asset_key=[*key_prefix, "diagnostic_and_instruction"],
    region_subfolder=region_subfolder,
    remote_file_regex=(
        r"diagnostic_and_instruction_(?P<subject>ela|math)_ytd_window\.csv"
    ),
    avro_schema=DIAGNOSTIC_AND_INSTRUCTION_SCHEMA,
    start_fiscal_year=2022,
    end_fiscal_year=2024,
)

assets = [
    diagnostic_results,
    instruction_by_lesson,
    instruction_by_lesson_pro,
    instructional_usage_data,
]
