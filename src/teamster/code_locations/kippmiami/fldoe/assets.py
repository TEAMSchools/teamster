from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippmiami.fldoe.schema import (
    EOC_SCHEMA,
    FAST_SCHEMA,
    FSA_SCHEMA,
    FTE_SCHEMA,
    SCIENCE_SCHEMA,
)
from teamster.libraries.sftp.assets import (
    build_sftp_file_asset,
    build_sftp_folder_asset,
)

fast = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "fldoe", "fast"],
    remote_dir_regex=(
        r"/data-team/kippmiami/fldoe/fast/(?P<school_year_term>SY\d+/PM\d)"
    ),
    remote_file_regex=(
        r"\w+-\w+_(?P<grade_level_subject>Grade\dFAST\w+)_StudentData_.+\.csv"
    ),
    ssh_resource_key="ssh_couchdrop",
    avro_schema=FAST_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "school_year_term": StaticPartitionsDefinition(
                sorted(
                    [
                        f"SY{str(year)[-2:]}/PM{term}"
                        for term in [1, 2, 3]
                        for year in range(2023, CURRENT_FISCAL_YEAR.fiscal_year + 1)
                    ]
                )
            ),
            "grade_level_subject": StaticPartitionsDefinition(
                sorted(
                    [
                        f"Grade{grade}FAST{subject}"
                        for subject in ["ELAReading", "Mathematics"]
                        for grade in [3, 4, 5, 6, 7, 8]
                    ]
                )
            ),
        }
    ),
)

eoc = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "fldoe", "eoc"],
    remote_dir_regex=(r"/data-team/kippmiami/fldoe/eoc/(?P<school_year_term>\d+)"),
    remote_file_regex=(
        r"\w+-\w+_(?P<grade_level_subject>[\w\.]+)EOC_StudentData_\d+\s[AP]M\.csv"
    ),
    ssh_resource_key="ssh_couchdrop",
    avro_schema=EOC_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "school_year_term": StaticPartitionsDefinition(
                [str(year) for year in range(2023, CURRENT_FISCAL_YEAR.fiscal_year)]
            ),
            "grade_level_subject": StaticPartitionsDefinition(
                ["Civics", "B.E.S.T.Algebra1"]
            ),
        }
    ),
)

science = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "fldoe", "science"],
    remote_dir_regex=r"/data-team/kippmiami/fldoe/science/(?P<school_year_term>\d+)",
    remote_file_regex=(
        r"\w+-\w+_Grade(?P<grade_level_subject>\d)Science_StudentData_\d+\s[AP]M\.csv"
    ),
    ssh_resource_key="ssh_couchdrop",
    avro_schema=SCIENCE_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "school_year_term": StaticPartitionsDefinition(
                [str(year) for year in range(2023, CURRENT_FISCAL_YEAR.fiscal_year)]
            ),
            "grade_level_subject": StaticPartitionsDefinition(["5", "8"]),
        }
    ),
)

fte = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "fldoe", "fte"],
    remote_dir_regex=(
        r"/data-team/kippmiami/fldoe/fte/SY(?P<school_year>\w+)/Survey (?P<survey>\d)"
    ),
    remote_file_regex=r".+\.pdf",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=FTE_SCHEMA,
    pdf_row_pattern=(
        r"\s+(?P<school_number>\d+)"
        r"\s+(?P<student_id>\d+)"
        r"\s+(?P<florida_student_id>[\dX]+)"
        r"\s+(?P<student_name>[\D]+)"
        r"\s+(?P<grade>\w+)"
        r"\s+(?P<fte_capped>[\d\.]+)"
        r"\s+(?P<fte_uncapped>[\d\.]+)"
    ),
    partitions_def=MultiPartitionsDefinition(
        {
            "school_year": StaticPartitionsDefinition(
                [
                    str(year)[-2:]
                    for year in range(2022, CURRENT_FISCAL_YEAR.fiscal_year + 1)
                ]
            ),
            "survey": StaticPartitionsDefinition(["2", "3"]),
        }
    ),
)

assets = [
    eoc,
    fast,
    fte,
    science,
]

# archived
fsa = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "fldoe", "fsa"],
    remote_dir_regex=r"/data-team/kippmiami/fldoe/fsa/student_scores",
    remote_file_regex=(
        r"FSA_(?P<school_year_term>\d+)SPR_\d+_SRS-E_"
        r"(?P<grade_level_subject>\w+)_SCHL\.csv"
    ),
    ssh_resource_key="ssh_couchdrop",
    avro_schema=FSA_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "school_year_term": StaticPartitionsDefinition(["21", "22"]),
            "grade_level_subject": StaticPartitionsDefinition(
                ["ELA_GR03", "SCI", "MATH", "ELA_GR04_10"]
            ),
        }
    ),
)
