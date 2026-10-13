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

# FLDOE moved the ordinal to the front of the standards columns in 2026-27:
# `Category` became `1. Category`. `FLDOECategories` already declares ordinals 1
# through 44. See #5283. `dict_reader_to_records` sorts replacements longest key
# first, so these beat the bare-ordinal strip below. Order here is irrelevant.
FAST_STANDARDS_REPLACEMENTS = [
    [f"{ordinal}. {label}", f"{slug}_{ordinal}"]
    for ordinal in range(1, 45)
    for label, slug in (
        ("Category", "category"),
        ("Benchmark", "benchmark"),
        ("Points Earned", "points_earned"),
        ("Points Possible", "points_possible"),
    )
]

# Every `N. <Prose> Performance` header slugifies to its target once the leading
# ordinal is gone, so one strip replaces the 21 pairs that used to be spelled out.
# The ordinal is not load-bearing: grades 7 and 8 already mapped `3. Geometric
# Reasoning Performance` and `4. Geometric Reasoning Performance` to one field.
# ponytail: strips `N. ` anywhere in a header, not just leading. No FLDOE header
# has one mid-string; anchor this if one ever ships.
FAST_ORDINAL_STRIP = [[f"{ordinal}. ", ""] for ordinal in range(1, 5)]

fast = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "fldoe", "fast"],
    remote_dir_regex=(
        r"/data-team/kippmiami/fldoe/fast/(?P<school_year_term>SY\d+/PM\d)"
    ),
    remote_file_regex=(
        r"[^/]+?_(?P<grade_level_subject>Grade\dFAST\w+)_StudentData_.+\.csv"
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
            # FLDOE added Grade 9 FAST ELA Reading in 2026-27 and sends no
            # Grade 9 mathematics file, so Grade 9 is listed on its own instead of
            # widening the grade/subject cross product. See #5283.
            "grade_level_subject": StaticPartitionsDefinition(
                sorted(
                    [
                        f"Grade{grade}FAST{subject}"
                        for subject in ["ELAReading", "Mathematics"]
                        for grade in [3, 4, 5, 6, 7, 8]
                    ]
                    + ["Grade9FASTELAReading"]
                )
            ),
        }
    ),
    slugify_replacements=[
        *FAST_STANDARDS_REPLACEMENTS,
        *FAST_ORDINAL_STRIP,
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
    slugify_replacements=[
        [
            "1. Expressions, Functions, and Data Analysis Performance",
            "field_1_expressions_functions_and_data_analysis_performance",
        ],
        [
            "2. Linear Relationships Performance",
            "field_2_linear_relationships_performance",
        ],
        [
            "3. Non-Linear Relationships Performance",
            "field_3_non_linear_relationships_performance",
        ],
        [
            "1. Origins and Purposes of Law and Government Performance",
            "field_1_origins_and_purposes_of_law_and_government_performance",
        ],
        [
            "2. Roles, Rights, and Responsibilities of Citizens Performance",
            "field_2_roles_rights_and_responsibilities_of_citizens_performance",
        ],
        [
            "3. Government Policies and Political Processes Performance",
            "field_3_government_policies_and_political_processes_performance",
        ],
        [
            "4. Organization and Function of Government Performance",
            "field_4_organization_and_function_of_government_performance",
        ],
    ],
)

science = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "fldoe", "science"],
    remote_dir_regex=r"/data-team/kippmiami/fldoe/science/(?P<school_year_term>\d+)",
    remote_file_regex=(
        r"[^/]+?_Grade(?P<grade_level_subject>\d)Science_StudentData_\d+\s[AP]M\.csv"
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
    slugify_replacements=[
        [
            "1. Nature of Science Performance",
            "field_1_nature_of_science_performance",
        ],
        [
            "2. Earth and Space Science Performance",
            "field_2_earth_and_space_science_performance",
        ],
        [
            "3. Physical Science Performance",
            "field_3_physical_science_performance",
        ],
        [
            "4. Life Science Performance",
            "field_4_life_science_performance",
        ],
    ],
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
