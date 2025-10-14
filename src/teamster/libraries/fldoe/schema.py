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
    district_use: str | None = None
    english_language_learner_ell_status: str | None = None
    enrolled_district: str | None = None
    enrolled_grade: str | None = None
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


class FLDOECategories(BaseModel):
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
    benchmark_36: str | None = None
    benchmark_37: str | None = None
    benchmark_38: str | None = None
    benchmark_39: str | None = None
    benchmark_4: str | None = None
    benchmark_40: str | None = None
    benchmark_41: str | None = None
    benchmark_42: str | None = None
    benchmark_43: str | None = None
    benchmark_44: str | None = None
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
    category_36: str | None = None
    category_37: str | None = None
    category_38: str | None = None
    category_39: str | None = None
    category_4: str | None = None
    category_40: str | None = None
    category_41: str | None = None
    category_42: str | None = None
    category_43: str | None = None
    category_44: str | None = None
    category_5: str | None = None
    category_6: str | None = None
    category_7: str | None = None
    category_8: str | None = None
    category_9: str | None = None
    category: str | None = None
    points_earned_1: str | None = None
    points_earned_10: str | None = None
    points_earned_11: str | None = None
    points_earned_12: str | None = None
    points_earned_13: str | None = None
    points_earned_14: str | None = None
    points_earned_15: str | None = None
    points_earned_16: str | None = None
    points_earned_17: str | None = None
    points_earned_18: str | None = None
    points_earned_19: str | None = None
    points_earned_2: str | None = None
    points_earned_20: str | None = None
    points_earned_21: str | None = None
    points_earned_22: str | None = None
    points_earned_23: str | None = None
    points_earned_24: str | None = None
    points_earned_25: str | None = None
    points_earned_26: str | None = None
    points_earned_27: str | None = None
    points_earned_28: str | None = None
    points_earned_29: str | None = None
    points_earned_3: str | None = None
    points_earned_30: str | None = None
    points_earned_31: str | None = None
    points_earned_32: str | None = None
    points_earned_33: str | None = None
    points_earned_34: str | None = None
    points_earned_35: str | None = None
    points_earned_36: str | None = None
    points_earned_37: str | None = None
    points_earned_38: str | None = None
    points_earned_39: str | None = None
    points_earned_4: str | None = None
    points_earned_40: str | None = None
    points_earned_41: str | None = None
    points_earned_42: str | None = None
    points_earned_43: str | None = None
    points_earned_44: str | None = None
    points_earned_5: str | None = None
    points_earned_6: str | None = None
    points_earned_7: str | None = None
    points_earned_8: str | None = None
    points_earned_9: str | None = None
    points_earned: str | None = None
    points_possible_1: str | None = None
    points_possible_10: str | None = None
    points_possible_11: str | None = None
    points_possible_12: str | None = None
    points_possible_13: str | None = None
    points_possible_14: str | None = None
    points_possible_15: str | None = None
    points_possible_16: str | None = None
    points_possible_17: str | None = None
    points_possible_18: str | None = None
    points_possible_19: str | None = None
    points_possible_2: str | None = None
    points_possible_20: str | None = None
    points_possible_21: str | None = None
    points_possible_22: str | None = None
    points_possible_23: str | None = None
    points_possible_24: str | None = None
    points_possible_25: str | None = None
    points_possible_26: str | None = None
    points_possible_27: str | None = None
    points_possible_28: str | None = None
    points_possible_29: str | None = None
    points_possible_3: str | None = None
    points_possible_30: str | None = None
    points_possible_31: str | None = None
    points_possible_32: str | None = None
    points_possible_33: str | None = None
    points_possible_34: str | None = None
    points_possible_35: str | None = None
    points_possible_36: str | None = None
    points_possible_37: str | None = None
    points_possible_38: str | None = None
    points_possible_39: str | None = None
    points_possible_4: str | None = None
    points_possible_40: str | None = None
    points_possible_41: str | None = None
    points_possible_42: str | None = None
    points_possible_43: str | None = None
    points_possible_44: str | None = None
    points_possible_5: str | None = None
    points_possible_6: str | None = None
    points_possible_7: str | None = None
    points_possible_8: str | None = None
    points_possible_9: str | None = None
    points_possible: str | None = None


class FAST(FLDOECore, FLDOECategories):
    fast_grade_3_ela_reading_achievement_level: str | None = None
    fast_grade_3_ela_reading_percentile_rank: str | None = None
    fast_grade_3_ela_reading_scale_score: str | None = None
    fast_grade_3_mathematics_achievement_level: str | None = None
    fast_grade_3_mathematics_percentile_rank: str | None = None
    fast_grade_3_mathematics_scale_score: str | None = None
    fast_grade_4_ela_reading_achievement_level: str | None = None
    fast_grade_4_ela_reading_percentile_rank: str | None = None
    fast_grade_4_ela_reading_scale_score: str | None = None
    fast_grade_4_mathematics_achievement_level: str | None = None
    fast_grade_4_mathematics_percentile_rank: str | None = None
    fast_grade_4_mathematics_scale_score: str | None = None
    fast_grade_5_ela_reading_achievement_level: str | None = None
    fast_grade_5_ela_reading_percentile_rank: str | None = None
    fast_grade_5_ela_reading_scale_score: str | None = None
    fast_grade_5_mathematics_achievement_level: str | None = None
    fast_grade_5_mathematics_percentile_rank: str | None = None
    fast_grade_5_mathematics_scale_score: str | None = None
    fast_grade_6_ela_reading_achievement_level: str | None = None
    fast_grade_6_ela_reading_percentile_rank: str | None = None
    fast_grade_6_ela_reading_scale_score: str | None = None
    fast_grade_6_mathematics_achievement_level: str | None = None
    fast_grade_6_mathematics_percentile_rank: str | None = None
    fast_grade_6_mathematics_scale_score: str | None = None
    fast_grade_7_ela_reading_achievement_level: str | None = None
    fast_grade_7_ela_reading_percentile_rank: str | None = None
    fast_grade_7_ela_reading_scale_score: str | None = None
    fast_grade_7_mathematics_achievement_level: str | None = None
    fast_grade_7_mathematics_percentile_rank: str | None = None
    fast_grade_7_mathematics_scale_score: str | None = None
    fast_grade_8_ela_reading_achievement_level: str | None = None
    fast_grade_8_ela_reading_percentile_rank: str | None = None
    fast_grade_8_ela_reading_scale_score: str | None = None
    fast_grade_8_mathematics_achievement_level: str | None = None
    fast_grade_8_mathematics_percentile_rank: str | None = None
    fast_grade_8_mathematics_scale_score: str | None = None
    grade_3_fast_ela_reading_achievement_level: str | None = None
    grade_3_fast_ela_reading_percentile_rank: str | None = None
    grade_3_fast_ela_reading_scale_score: str | str | None = None
    grade_3_fast_mathematics_achievement_level: str | None = None
    grade_3_fast_mathematics_percentile_rank: str | None = None
    grade_3_fast_mathematics_scale_score: str | str | None = None
    grade_4_fast_ela_reading_achievement_level: str | None = None
    grade_4_fast_ela_reading_percentile_rank: str | None = None
    grade_4_fast_ela_reading_scale_score: str | None = None
    grade_4_fast_mathematics_achievement_level: str | None = None
    grade_4_fast_mathematics_percentile_rank: str | None = None
    grade_4_fast_mathematics_scale_score: str | None = None
    grade_5_fast_ela_reading_achievement_level: str | None = None
    grade_5_fast_ela_reading_percentile_rank: str | None = None
    grade_5_fast_ela_reading_scale_score: str | None = None
    grade_5_fast_mathematics_achievement_level: str | None = None
    grade_5_fast_mathematics_percentile_rank: str | None = None
    grade_5_fast_mathematics_scale_score: str | None = None
    grade_6_fast_ela_reading_achievement_level: str | None = None
    grade_6_fast_ela_reading_percentile_rank: str | None = None
    grade_6_fast_ela_reading_scale_score: str | None = None
    grade_6_fast_mathematics_achievement_level: str | None = None
    grade_6_fast_mathematics_percentile_rank: str | None = None
    grade_6_fast_mathematics_scale_score: str | None = None
    grade_7_fast_ela_reading_achievement_level: str | None = None
    grade_7_fast_ela_reading_percentile_rank: str | None = None
    grade_7_fast_ela_reading_scale_score: str | None = None
    grade_7_fast_mathematics_achievement_level: str | None = None
    grade_7_fast_mathematics_percentile_rank: str | None = None
    grade_7_fast_mathematics_scale_score: str | None = None
    grade_8_fast_ela_reading_achievement_level: str | None = None
    grade_8_fast_ela_reading_percentile_rank: str | None = None
    grade_8_fast_ela_reading_scale_score: str | str | None = None
    grade_8_fast_mathematics_achievement_level: str | None = None
    grade_8_fast_mathematics_percentile_rank: str | None = None
    grade_8_fast_mathematics_scale_score: str | None = None

    algebraic_reasoning_performance: str | None = None
    data_analysis_and_probability_performance: str | None = None
    fractional_reasoning_performance: str | None = None
    geometric_reasoning_data_analysis_and_probability_performance: str | None = None
    geometric_reasoning_performance: str | None = None
    geometric_reasoning_measurement_and_data_analysis_and_probability_performance: (
        str | None
    ) = None
    linear_relationships_data_analysis_and_functions_performance: str | None = None
    number_sense_and_additive_reasoning_performance: str | None = None
    number_sense_and_operations_with_whole_numbers_performance: str | None = None
    number_sense_and_operations_performance: str | None = None
    number_sense_and_operations_and_algebraic_reasoning_performance: str | None = None
    number_sense_and_operations_and_probability_performance: str | None = None
    number_sense_and_multiplicative_reasoning_performance: str | None = None
    number_sense_and_operations_with_fractions_and_decimals_performance: str | None = (
        None
    )
    proportional_reasoning_and_relationships_performance: str | None = None
    reading_prose_and_poetry_performance: str | None = None
    reading_informational_text_performance: str | None = None
    reading_across_genres_vocabulary_performance: str | None = None


class EOC(FLDOECore, FLDOECategories):
    b_e_s_t_algebra_1_eoc_achievement_level: str | None = None
    b_e_s_t_algebra_1_eoc_scale_score: str | None = None
    civics_eoc_achievement_level: str | None = None
    civics_eoc_scale_score: str | None = None

    field_1_origins_and_purposes_of_law_and_government_performance: str | None = Field(
        default=None,
        validation_alias="1_origins_and_purposes_of_law_and_government_performance",
    )
    field_2_roles_rights_and_responsibilities_of_citizens_performance: str | None = (
        Field(
            default=None,
            validation_alias=(
                "2_roles_rights_and_responsibilities_of_citizens_performance"
            ),
        )
    )
    field_3_government_policies_and_political_processes_performance: str | None = Field(
        default=None,
        validation_alias="3_government_policies_and_political_processes_performance",
    )
    field_4_organization_and_function_of_government_performance: str | None = Field(
        default=None,
        validation_alias="4_organization_and_function_of_government_performance",
    )

    field_1_expressions_functions_and_data_analysis_performance: str | None = Field(
        default=None,
        validation_alias="1_expressions_functions_and_data_analysis_performance",
    )
    field_2_linear_relationships_performance: str | None = Field(
        default=None, validation_alias="2_linear_relationships_performance"
    )
    field_3_non_linear_relationships_performance: str | None = Field(
        default=None, validation_alias="3_non_linear_relationships_performance"
    )


class Science(FLDOECore, FLDOECategories):
    grade_5_science_achievement_level: str | None = None
    grade_5_science_scale_score: str | None = None
    grade_8_science_achievement_level: str | None = None
    grade_8_science_scale_score: str | None = None

    field_1_nature_of_science_performance: str | None = Field(
        None, validation_alias="1_nature_of_science_performance"
    )
    field_2_earth_and_space_science_performance: str | None = Field(
        None, validation_alias="2_earth_and_space_science_performance"
    )
    field_3_physical_science_performance: str | None = Field(
        None, validation_alias="3_physical_science_performance"
    )
    field_4_life_science_performance: str | None = Field(
        None, validation_alias="4_life_science_performance"
    )


class FSA(BaseModel):
    conditioncode: str | None = None
    dis: str | None = None
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
    performancelevel: str | None = None
    rptstatus: str | None = None
    scalescore: str | None = None
    sch: str | None = None
    schname: str | None = None
    schoolyear: str | None = None
    scoreflag_r: str | None = None
    scoreflag_w: str | None = None
    scoreflag: str | None = None
    testname: str | None = None
    tgrade: str | None = None

    field_pass: str | None = Field(default=None, alias="pass")
