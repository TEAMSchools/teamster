from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.code_locations.kippmiami.fldoe.schema import (
    EOC_SCHEMA,
    FAST_SCHEMA,
    FSA_SCHEMA,
    SCIENCE_SCHEMA,
)
from teamster.libraries.sftp.assets import (
    build_sftp_file_asset,
    build_sftp_folder_asset,
)

fast = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "fldoe", "fast"],
    remote_dir_regex=r"/data-team/kippmiami/fldoe/fast/(?P<school_year_term>\d+/PM\d)",
    remote_file_regex=(
        r"\w+-\w+_(?P<grade_level_subject>Grade\dFAST\w+)_StudentData_.+\.csv"
    ),
    ssh_resource_key="ssh_couchdrop",
    avro_schema=FAST_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "school_year_term": StaticPartitionsDefinition(
                ["SY23/PM1", "SY23/PM2", "SY23/PM3", "SY24/PM1", "SY24/PM2", "SY24/PM3"]
            ),
            "grade_level_subject": StaticPartitionsDefinition(
                [
                    "Grade3FASTELAReading",
                    "Grade3FASTMathematics",
                    "Grade4FASTELAReading",
                    "Grade4FASTMathematics",
                    "Grade5FASTELAReading",
                    "Grade5FASTMathematics",
                    "Grade6FASTELAReading",
                    "Grade6FASTMathematics",
                    "Grade7FASTELAReading",
                    "Grade7FASTMathematics",
                    "Grade8FASTELAReading",
                    "Grade8FASTMathematics",
                ]
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
            "school_year_term": StaticPartitionsDefinition(["2023"]),
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
            "school_year_term": StaticPartitionsDefinition(["2023"]),
            "grade_level_subject": StaticPartitionsDefinition(["5", "8"]),
        }
    ),
)

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

assets = [
    eoc,
    fast,
    fsa,
    science,
]
