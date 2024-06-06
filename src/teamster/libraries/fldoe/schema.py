from pydantic import BaseModel, Field


class FLDOECore(BaseModel):
    date_taken: str | None = None
    english_language_learner_ell_status: str | None = None
    enrolled_district: str | None = None
    enrolled_school: str | None = None
    ethnicity: str | None = None
    gender_k_12: str | None = None
    gender_postsecondary_only: str | None = None
    local_id: str | None = None
    primary_exceptionality: str | None = None
    section_504: str | None = None
    student_dob: str | None = None
    student_id: str | None = None
    student_name: str | None = None
    test_completion_date: str | None = None
    test_oppnumber: str | None = None
    test_reason: str | None = None
    testing_location: str | None = None
    unnamed_23: str | None = None
    unnamed_24: str | None = None
    unnamed_25: str | None = None

    enrolled_grade: int | float | None = None


class FAST(FLDOECore):
    fast_grade_3_ela_reading_achievement_level: str | None = None
    fast_grade_3_mathematics_achievement_level: str | None = None
    fast_grade_4_ela_reading_achievement_level: str | None = None
    fast_grade_4_mathematics_achievement_level: str | None = None
    fast_grade_5_ela_reading_achievement_level: str | None = None
    fast_grade_5_mathematics_achievement_level: str | None = None
    fast_grade_6_ela_reading_achievement_level: str | None = None
    fast_grade_6_mathematics_achievement_level: str | None = None
    fast_grade_7_ela_reading_achievement_level: str | None = None
    fast_grade_7_mathematics_achievement_level: str | None = None
    fast_grade_8_ela_reading_achievement_level: str | None = None
    fast_grade_8_mathematics_achievement_level: str | None = None
    grade_3_fast_ela_reading_achievement_level: str | None = None
    grade_3_fast_mathematics_achievement_level: str | None = None
    grade_4_fast_ela_reading_achievement_level: str | None = None
    grade_4_fast_mathematics_achievement_level: str | None = None
    grade_5_fast_ela_reading_achievement_level: str | None = None
    grade_5_fast_mathematics_achievement_level: str | None = None
    grade_6_fast_ela_reading_achievement_level: str | None = None
    grade_6_fast_mathematics_achievement_level: str | None = None
    grade_7_fast_ela_reading_achievement_level: str | None = None
    grade_7_fast_mathematics_achievement_level: str | None = None
    grade_8_fast_ela_reading_achievement_level: str | None = None
    grade_8_fast_mathematics_achievement_level: str | None = None

    fast_grade_3_ela_reading_percentile_rank: str | int | None = None
    fast_grade_3_ela_reading_scale_score: str | int | None = None
    fast_grade_3_mathematics_percentile_rank: str | int | None = None
    fast_grade_3_mathematics_scale_score: str | int | None = None
    fast_grade_4_ela_reading_percentile_rank: str | int | None = None
    fast_grade_4_ela_reading_scale_score: str | int | None = None
    fast_grade_4_mathematics_percentile_rank: str | int | None = None
    fast_grade_4_mathematics_scale_score: str | int | None = None
    fast_grade_5_ela_reading_percentile_rank: str | int | None = None
    fast_grade_5_ela_reading_scale_score: str | int | None = None
    fast_grade_5_mathematics_percentile_rank: str | int | None = None
    fast_grade_5_mathematics_scale_score: str | int | None = None
    fast_grade_6_ela_reading_percentile_rank: str | int | None = None
    fast_grade_6_ela_reading_scale_score: str | int | None = None
    fast_grade_6_mathematics_percentile_rank: str | int | None = None
    fast_grade_6_mathematics_scale_score: str | int | None = None
    fast_grade_7_ela_reading_percentile_rank: str | int | None = None
    fast_grade_7_ela_reading_scale_score: str | int | None = None
    fast_grade_7_mathematics_percentile_rank: str | int | None = None
    fast_grade_7_mathematics_scale_score: str | int | None = None
    fast_grade_8_ela_reading_percentile_rank: str | int | None = None
    fast_grade_8_ela_reading_scale_score: str | int | None = None
    fast_grade_8_mathematics_percentile_rank: str | int | None = None
    fast_grade_8_mathematics_scale_score: str | int | None = None
    grade_3_fast_ela_reading_percentile_rank: str | int | None = None
    grade_3_fast_ela_reading_scale_score: int | str | None = None
    grade_3_fast_mathematics_percentile_rank: str | int | None = None
    grade_3_fast_mathematics_scale_score: int | str | None = None
    grade_4_fast_ela_reading_percentile_rank: str | int | None = None
    grade_4_fast_ela_reading_scale_score: str | int | None = None
    grade_4_fast_mathematics_percentile_rank: str | int | None = None
    grade_4_fast_mathematics_scale_score: str | int | None = None
    grade_5_fast_ela_reading_percentile_rank: str | int | None = None
    grade_5_fast_ela_reading_scale_score: str | int | None = None
    grade_5_fast_mathematics_percentile_rank: str | int | None = None
    grade_5_fast_mathematics_scale_score: str | int | None = None
    grade_6_fast_ela_reading_percentile_rank: str | int | None = None
    grade_6_fast_ela_reading_scale_score: str | int | None = None
    grade_6_fast_mathematics_percentile_rank: str | int | None = None
    grade_6_fast_mathematics_scale_score: str | int | None = None
    grade_7_fast_ela_reading_percentile_rank: str | int | None = None
    grade_7_fast_ela_reading_scale_score: str | int | None = None
    grade_7_fast_mathematics_percentile_rank: str | int | None = None
    grade_7_fast_mathematics_scale_score: str | int | None = None
    grade_8_fast_ela_reading_percentile_rank: str | int | None = None
    grade_8_fast_ela_reading_scale_score: int | str | None = None
    grade_8_fast_mathematics_percentile_rank: str | int | None = None
    grade_8_fast_mathematics_scale_score: str | int | None = None

    field_1_ela_reading: str | None = Field(
        default=None, alias="1_reading_prose_and_poetry_performance"
    )
    field_2_ela_reading: str | None = Field(
        default=None, alias="2_reading_informational_text_performance"
    )
    field_3_ela_reading: str | None = Field(
        default=None, alias="3_reading_across_genres_vocabulary_performance"
    )

    field_1_mathematics_1: str | None = Field(
        default=None, alias="1_number_sense_and_additive_reasoning_performance"
    )
    field_1_mathematics_2: str | None = Field(
        default=None,
        alias="1_number_sense_and_operations_with_whole_numbers_performance",
    )
    field_1_mathematics_3: str | None = Field(
        default=None, alias="1_number_sense_and_operations_performance"
    )
    field_1_mathematics_4: str | None = Field(
        default=None,
        alias="1_number_sense_and_operations_and_algebraic_reasoning_performance",
    )
    field_1_mathematics_5: str | None = Field(
        default=None, alias="1_number_sense_and_operations_and_probability_performance"
    )

    field_2_mathematics_1: str | None = Field(
        default=None, alias="2_number_sense_and_multiplicative_reasoning_performance"
    )
    field_2_mathematics_2: str | None = Field(
        default=None,
        alias="2_number_sense_and_operations_with_fractions_and_decimals_performance",
    )
    field_2_mathematics_3: str | None = Field(
        default=None, alias="2_algebraic_reasoning_performance"
    )
    field_2_mathematics_4: str | None = Field(
        default=None, alias="2_proportional_reasoning_and_relationships_performance"
    )

    field_3_mathematics_1: str | None = Field(
        default=None, alias="3_fractional_reasoning_performance"
    )
    field_3_mathematics_2: str | None = Field(
        default=None,
        alias="3_geometric_reasoning_measurement_and_data_analysis_and_probability_performance",
    )
    field_3_mathematics_3: str | None = Field(
        default=None, alias="3_algebraic_reasoning_performance"
    )
    field_3_mathematics_4: str | None = Field(
        default=None,
        alias="3_geometric_reasoning_data_analysis_and_probability_performance",
    )
    field_3_mathematics_5: str | None = Field(
        default=None, alias="3_geometric_reasoning_performance"
    )
    field_3_mathematics_6: str | None = Field(
        default=None,
        alias="3_linear_relationships_data_analysis_and_functions_performance",
    )

    field_4_mathematics_1: str | None = Field(
        default=None, alias="4_data_analysis_and_probability_performance"
    )
    field_4_mathematics_2: str | None = Field(
        default=None, alias="4_geometric_reasoning_performance"
    )
    field_4_mathematics_3: str | None = Field(
        default=None,
        alias="4_geometric_reasoning_measurement_and_data_analysis_and_probability_performance",
    )


class EOC(FLDOECore):
    b_e_s_t_algebra_1_eoc_achievement_level: str | None = None
    b_e_s_t_algebra_1_eoc_scale_score: str | None = None
    civics_eoc_achievement_level: str | None = None
    civics_eoc_scale_score: str | None = None

    field_1_civics: str | None = Field(
        default=None, alias="1_origins_and_purposes_of_law_and_government_performance"
    )
    field_2_civics: str | None = Field(
        default=None,
        alias="2_roles_rights_and_responsibilities_of_citizens_performance",
    )
    field_3_civics: str | None = Field(
        default=None, alias="3_government_policies_and_political_processes_performance"
    )
    field_4_civics: str | None = Field(
        default=None, alias="4_organization_and_function_of_government_performance"
    )

    field_1_algebra_i: str | None = Field(
        None, alias="1_expressions_functions_and_data_analysis_performance"
    )
    field_2_algebra_i: str | None = Field(
        None, alias="2_linear_relationships_performance"
    )
    field_3_algebra_i: str | None = Field(
        None, alias="3_non_linear_relationships_performance"
    )


class Science(FLDOECore):
    grade_5_science_achievement_level: str | None = None
    grade_5_science_scale_score: int | None = None
    grade_8_science_achievement_level: str | None = None
    grade_8_science_scale_score: int | None = None

    field_1_science: str | None = Field(None, alias="1_nature_of_science_performance")
    field_2_science: str | None = Field(
        None, alias="2_earth_and_space_science_performance"
    )
    field_3_science: str | None = Field(None, alias="3_physical_science_performance")
    field_4_science: str | None = Field(None, alias="4_life_science_performance")


class FSA(BaseModel):
    conditioncode: str | None = None
    dis: int | None = None
    disname: str | None = None
    earn_wd1_ptpos_wd1: str | None = None
    earn_wd2_ptpos_wd2: str | None = None
    earn_wd3_ptpos_wd3: str | None = None
    earn1_ptpos1: str | None = None
    earn2_ptpos2: str | None = None
    earn3_ptpos3: str | None = None
    earn4_ptpos4: str | None = None
    earn5_ptpos5: str | None = None
    firstname: str | None = None
    fleid: str | None = None
    lastname: str | None = None
    mi: str | None = None
    rptstatus: str | None = None
    sch: int | None = None
    schname: str | None = None
    schoolyear: int | None = None
    scoreflag_w: str | None = None
    scoreflag: int | None = None
    testname: str | None = None
    tgrade: int | None = None

    performancelevel: int | str | None = None
    scalescore: int | str | None = None
    scoreflag_r: int | str | None = None

    field_pass: str | None = Field(default=None, alias="pass")
