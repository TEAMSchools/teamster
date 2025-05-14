from pydantic import BaseModel, Field


class FTE(BaseModel):
    school_number: str | None = None
    student_id: str | None = None
    florida_student_id: str | None = None
    student_name: str | None = None
    grade: str | None = None
    fte_capped: str | None = None
    fte_uncapped: str | None = None


class FLDOECore(BaseModel):
    date_taken: str | None = None
    district_use: int | None = None
    english_language_learner_ell_status: str | None = None
    enrolled_district: str | None = None
    enrolled_school: str | None = None
    ethnicity: str | None = None
    gender_k_12: str | None = None
    gender_postsecondary_only: str | None = None
    local_id: str | None = None
    primary_exceptionality: str | None = None
    section_504: str | None = None
    sex: str | None = None
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

    benchmark_1: str | None = None
    benchmark_10: str | None = None
    benchmark_11: str | None = None
    benchmark_12: str | None = None
    benchmark_13: str | None = None
    benchmark_14: str | None = None
    benchmark_15: str | None = None
    benchmark_16: str | None = None
    benchmark_17: str | None = None
    benchmark_18: str | None = None
    benchmark_19: str | None = None
    benchmark_2: str | None = None
    benchmark_20: str | None = None
    benchmark_21: str | None = None
    benchmark_22: str | None = None
    benchmark_23: str | None = None
    benchmark_24: str | None = None
    benchmark_25: str | None = None
    benchmark_26: str | None = None
    benchmark_27: str | None = None
    benchmark_28: str | None = None
    benchmark_29: str | None = None
    benchmark_3: str | None = None
    benchmark_30: str | None = None
    benchmark_31: str | None = None
    benchmark_32: str | None = None
    benchmark_33: str | None = None
    benchmark_34: str | None = None
    benchmark_35: str | None = None
    benchmark_4: str | None = None
    benchmark_5: str | None = None
    benchmark_6: str | None = None
    benchmark_7: str | None = None
    benchmark_8: str | None = None
    benchmark_9: str | None = None
    benchmark: str | None = None
    category_1: str | None = None
    category_10: str | None = None
    category_11: str | None = None
    category_12: str | None = None
    category_13: str | None = None
    category_14: str | None = None
    category_15: str | None = None
    category_16: str | None = None
    category_17: str | None = None
    category_18: str | None = None
    category_19: str | None = None
    category_2: str | None = None
    category_20: str | None = None
    category_21: str | None = None
    category_22: str | None = None
    category_23: str | None = None
    category_24: str | None = None
    category_25: str | None = None
    category_26: str | None = None
    category_27: str | None = None
    category_28: str | None = None
    category_29: str | None = None
    category_3: str | None = None
    category_30: str | None = None
    category_31: str | None = None
    category_32: str | None = None
    category_33: str | None = None
    category_34: str | None = None
    category_35: str | None = None
    category_4: str | None = None
    category_5: str | None = None
    category_6: str | None = None
    category_7: str | None = None
    category_8: str | None = None
    category_9: str | None = None
    category: str | None = None
    points_earned_1: int | None = None
    points_earned_10: int | None = None
    points_earned_11: int | None = None
    points_earned_12: int | None = None
    points_earned_13: int | None = None
    points_earned_14: int | None = None
    points_earned_15: int | None = None
    points_earned_16: int | None = None
    points_earned_17: int | None = None
    points_earned_18: int | None = None
    points_earned_19: int | None = None
    points_earned_2: int | None = None
    points_earned_20: int | None = None
    points_earned_21: int | None = None
    points_earned_22: int | None = None
    points_earned_23: int | None = None
    points_earned_24: int | None = None
    points_earned_25: int | None = None
    points_earned_26: int | None = None
    points_earned_27: int | None = None
    points_earned_28: int | None = None
    points_earned_29: int | None = None
    points_earned_3: int | None = None
    points_earned_30: int | None = None
    points_earned_31: int | None = None
    points_earned_32: int | None = None
    points_earned_33: int | None = None
    points_earned_34: int | None = None
    points_earned_35: float | None = None
    points_earned_4: int | None = None
    points_earned_5: int | None = None
    points_earned_6: int | None = None
    points_earned_7: int | None = None
    points_earned_8: int | None = None
    points_earned_9: int | None = None
    points_earned: int | None = None
    points_possible_1: int | None = None
    points_possible_10: int | None = None
    points_possible_11: int | None = None
    points_possible_12: int | None = None
    points_possible_13: int | None = None
    points_possible_14: int | None = None
    points_possible_15: int | None = None
    points_possible_16: int | None = None
    points_possible_17: int | None = None
    points_possible_18: int | None = None
    points_possible_19: int | None = None
    points_possible_2: int | None = None
    points_possible_20: int | None = None
    points_possible_21: int | None = None
    points_possible_22: int | None = None
    points_possible_23: int | None = None
    points_possible_24: int | None = None
    points_possible_25: int | None = None
    points_possible_26: int | None = None
    points_possible_27: int | None = None
    points_possible_28: int | None = None
    points_possible_29: int | None = None
    points_possible_3: int | None = None
    points_possible_30: int | None = None
    points_possible_31: int | None = None
    points_possible_32: int | None = None
    points_possible_33: int | None = None
    points_possible_34: int | None = None
    points_possible_35: float | None = None
    points_possible_4: int | None = None
    points_possible_5: int | None = None
    points_possible_6: int | None = None
    points_possible_7: int | None = None
    points_possible_8: int | None = None
    points_possible_9: int | None = None
    points_possible: int | None = None

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
