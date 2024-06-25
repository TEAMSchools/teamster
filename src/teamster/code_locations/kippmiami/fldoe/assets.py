from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.code_locations.kippmiami.fldoe.schema import (
    EOC_SCHEMA,
    FAST_SCHEMA,
    FSA_SCHEMA,
    SCIENCE_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_asset

fast = build_sftp_asset(
    asset_key=[CODE_LOCATION, "fldoe", "fast"],
    remote_dir="/data-team/kippmiami/fldoe/fast",
    remote_file_regex=r"\d+\/PM\d\/\w+-\w+(?P<grade_level_subject>Grade\dFAST[A-Za-z]+)_StudentData_(?P<school_year_term>SY\d+PM\d)\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=FAST_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "school_year_term": StaticPartitionsDefinition(
                ["SY23PM1", "SY23PM2", "SY23PM3", "SY24PM1", "SY24PM2", "SY24PM3"]
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

eoc = build_sftp_asset(
    asset_key=[CODE_LOCATION, "fldoe", "eoc"],
    remote_dir="/data-team/kippmiami/fldoe/eoc",
    remote_file_regex=r"(?P<school_year_term>\d+)\/[A-Z]+-[A-Z]+_(?P<grade_level_subject>[\w\.]+)EOC_StudentData_\d+\s[AP]M\.csv",
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

science = build_sftp_asset(
    asset_key=[CODE_LOCATION, "fldoe", "science"],
    remote_dir="/data-team/kippmiami/fldoe/science",
    remote_file_regex=r"(?P<school_year_term>\d+)\/\w+-\w+Grade(?P<grade_level_subject>\d)Science_StudentData_\d+\s[AP]M\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=SCIENCE_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "school_year_term": StaticPartitionsDefinition(["2023"]),
            "grade_level_subject": StaticPartitionsDefinition(["5", "8"]),
        }
    ),
)

fsa = build_sftp_asset(
    asset_key=[CODE_LOCATION, "fldoe", "fsa"],
    remote_dir="/data-team/kippmiami/fldoe/fsa/student_scores",
    remote_file_regex=r"FSA_(?P<school_year_term>\d+)SPR_\d+_SRS-E_(?P<grade_level_subject>\w+)_SCHL\.csv",
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
