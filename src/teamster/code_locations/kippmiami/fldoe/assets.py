from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippmiami.fldoe.schema import (
    EOC_SCHEMA,
    FAST_SCHEMA,
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
    slugify_replacements=[
        [
            "1. Number Sense and Additive Reasoning Performance",
            "number_sense_and_additive_reasoning_performance",
        ],
        [
            "2. Number Sense and Multiplicative Reasoning Performance",
            "number_sense_and_multiplicative_reasoning_performance",
        ],
        [
            "3. Fractional Reasoning Performance",
            "fractional_reasoning_performance",
        ],
        [
            "4. Geometric Reasoning, Measurement, and Data Analysis and Probability Performance",
            "geometric_reasoning_measurement_and_data_analysis_and_probability_performance",
        ],
        [
            "1. Reading Prose and Poetry Performance",
            "reading_prose_and_poetry_performance",
        ],
        [
            "2. Reading Informational Text Performance",
            "reading_informational_text_performance",
        ],
        [
            "3. Reading Across Genres & Vocabulary Performance",
            "reading_across_genres_vocabulary_performance",
        ],
        [
            "1. Number Sense and Operations with Whole Numbers Performance",
            "number_sense_and_operations_with_whole_numbers_performance",
        ],
        [
            "2. Number Sense and Operations with Fractions and Decimals Performance",
            "number_sense_and_operations_with_fractions_and_decimals_performance",
        ],
        [
            "3. Geometric Reasoning, Measurement, and Data Analysis and Probability Performance",
            "geometric_reasoning_measurement_and_data_analysis_and_probability_performance",
        ],
        [
            "3. Algebraic Reasoning Performance",
            "algebraic_reasoning_performance",
        ],
        [
            "1. Number Sense and Operations Performance",
            "number_sense_and_operations_performance",
        ],
        [
            "2. Algebraic Reasoning Performance",
            "algebraic_reasoning_performance",
        ],
        [
            "3. Geometric Reasoning, Data Analysis, and Probability Performance",
            "geometric_reasoning_data_analysis_and_probability_performance",
        ],
        [
            "1. Number Sense and Operations and Algebraic Reasoning Performance",
            "number_sense_and_operations_and_algebraic_reasoning_performance",
        ],
        [
            "2. Proportional Reasoning and Relationships Performance",
            "proportional_reasoning_and_relationships_performance",
        ],
        [
            "3. Geometric Reasoning Performance",
            "geometric_reasoning_performance",
        ],
        [
            "4. Data Analysis and Probability Performance",
            "data_analysis_and_probability_performance",
        ],
        [
            "1. Number Sense and Operations and Probability Performance",
            "number_sense_and_operations_and_probability_performance",
        ],
        [
            "3. Linear Relationships, Data Analysis and Functions Performance",
            "linear_relationships_data_analysis_and_functions_performance",
        ],
        [
            "4. Geometric Reasoning Performance",
            "geometric_reasoning_performance",
        ],
    ],
)

eoc = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "fldoe", "eoc"],
    remote_dir_regex=(
        r"/data-team/kippmiami/fldoe/eoc/(?P<school_year_term>\d+)/"
        r"(?P<grade_level_subject>[\w\.]+)"
    ),
    remote_file_regex=r".+\.csv$",
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
