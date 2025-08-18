from pydantic import AliasChoices, BaseModel, Field

FILLER_FIELD = Field(
    default=None,
    validation_alias=AliasChoices(
        "filler_1",
        "filler_10",
        "filler_11",
        "filler_12",
        "filler_13",
        "filler_14",
        "filler_15",
        "filler_16",
        "filler_17",
        "filler_18",
        "filler_19",
        "filler_2",
        "filler_20",
        "filler_21",
        "filler_22",
        "filler_23",
        "filler_24",
        "filler_25",
        "filler_26",
        "filler_27",
        "filler_28",
        "filler_29",
        "filler_3",
        "filler_30",
        "filler_31",
        "filler_32",
        "filler_33",
        "filler_34",
        "filler_35",
        "filler_36",
        "filler_37",
        "filler_38",
        "filler_39",
        "filler_4",
        "filler_40",
        "filler_41",
        "filler_42",
        "filler_43",
        "filler_44",
        "filler_45",
        "filler_46",
        "filler_47",
        "filler_48",
        "filler_49",
        "filler_5",
        "filler_50",
        "filler_51",
        "filler_52",
        "filler_53",
        "filler_54",
        "filler_55",
        "filler_56",
        "filler_57",
        "filler_58",
        "filler_59",
        "filler_6",
        "filler_60",
        "filler_61",
        "filler_62",
        "filler_63",
        "filler_64",
        "filler_65",
        "filler_66",
        "filler_67",
        "filler_68",
        "filler_69",
        "filler_7",
        "filler_8",
        "filler_9",
        "filler",
    ),
)


class PSAT(BaseModel):
    address_city: str | None = None
    address_country: str | None = None
    address_county: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    address_province: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    ai_code: str | None = None
    ai_name: str | None = None
    ap_arthis: str | None = None
    ap_bio: str | None = None
    ap_calc: str | None = None
    ap_chem: str | None = None
    ap_compgovpol: str | None = None
    ap_compsci: str | None = None
    ap_compsciprin: str | None = None
    ap_englang: str | None = None
    ap_englit: str | None = None
    ap_envsci: str | None = None
    ap_eurhist: str | None = None
    ap_humgeo: str | None = None
    ap_macecon: str | None = None
    ap_micecon: str | None = None
    ap_music: str | None = None
    ap_physi: str | None = None
    ap_physmag: str | None = None
    ap_physmech: str | None = None
    ap_psych: str | None = None
    ap_seminar: str | None = None
    ap_stat: str | None = None
    ap_usgovpol: str | None = None
    ap_ushist: str | None = None
    ap_wrldhist: str | None = None
    birth_date: str | None = None
    cb_id: str | None = None
    cohort_year: str | None = None
    derived_aggregate_race_eth: str | None = None
    district_name: str | None = None
    district_student_id: str | None = None
    ebrw_ccr_benchmark: str | None = None
    email: str | None = None
    foreign_address: str | None = None
    form_code: str | None = None
    gender: str | None = None
    gpo: str | None = None
    grad_date: str | None = None
    homeschool: str | None = None
    hs_student: str | None = None
    latest_access_cd: str | None = None
    latest_psat_adv_math: str | None = None
    latest_psat_comm_evidence: str | None = None
    latest_psat_date: str | None = None
    latest_psat_ebrw: str | None = None
    latest_psat_eng_convent: str | None = None
    latest_psat_expr_ideas: str | None = None
    latest_psat_grade: str | None = None
    latest_psat_heart_algebra: str | None = None
    latest_psat_hist_socst_cross: str | None = None
    latest_psat_ks_math_advanced: str | None = None
    latest_psat_ks_math_algebra: str | None = None
    latest_psat_ks_math_geometry: str | None = None
    latest_psat_ks_math_problemsolving: str | None = None
    latest_psat_ks_math_section: str | None = None
    latest_psat_ks_reading_craft: str | None = None
    latest_psat_ks_reading_expression: str | None = None
    latest_psat_ks_reading_information: str | None = None
    latest_psat_ks_reading_section: str | None = None
    latest_psat_ks_reading_standard: str | None = None
    latest_psat_math_section: str | None = None
    latest_psat_math_test: str | None = None
    latest_psat_probslv_data: str | None = None
    latest_psat_reading: str | None = None
    latest_psat_sci_cross: str | None = None
    latest_psat_total: str | None = None
    latest_psat_words_context: str | None = None
    latest_psat_writ_lang: str | None = None
    latest_record_locator: str | None = None
    latest_reg_num: str | None = None
    major_first: str | None = None
    math_c_ques_correct: str | None = None
    math_c_ques_incorrect: str | None = None
    math_c_ques_omit: str | None = None
    math_ccr_benchmark: str | None = None
    math_nc_ques_correct: str | None = None
    math_nc_ques_incorrect: str | None = None
    math_nc_ques_omit: str | None = None
    name_first: str | None = None
    name_last: str | None = None
    name_mi: str | None = None
    national_merit: str | None = None
    num_math_cmc_ques: str | None = None
    num_math_cpr_ques: str | None = None
    num_math_ncmc_ques: str | None = None
    num_math_ncpr_ques: str | None = None
    num_reading_ques: str | None = None
    num_writlang_ques: str | None = None
    percentile_country_math: str | None = None
    percentile_country_rw: str | None = None
    percentile_country_total: str | None = None
    percentile_natrep_psat_adv_math: str | None = None
    percentile_natrep_psat_comm_evidence: str | None = None
    percentile_natrep_psat_ebrw: str | None = None
    percentile_natrep_psat_eng_convent: str | None = None
    percentile_natrep_psat_expr_ideas: str | None = None
    percentile_natrep_psat_heart_algebra: str | None = None
    percentile_natrep_psat_hist_socst_cross: str | None = None
    percentile_natrep_psat_math_section: str | None = None
    percentile_natrep_psat_math_test: str | None = None
    percentile_natrep_psat_probslv_data: str | None = None
    percentile_natrep_psat_reading: str | None = None
    percentile_natrep_psat_sci_cross: str | None = None
    percentile_natrep_psat_total: str | None = None
    percentile_natrep_psat_words_context: str | None = None
    percentile_natrep_psat_writ_lang: str | None = None
    percentile_natuser_psat_adv_math: str | None = None
    percentile_natuser_psat_comm_evidence: str | None = None
    percentile_natuser_psat_ebrw: str | None = None
    percentile_natuser_psat_eng_convent: str | None = None
    percentile_natuser_psat_expr_ideas: str | None = None
    percentile_natuser_psat_heart_algebra: str | None = None
    percentile_natuser_psat_hist_socst_cross: str | None = None
    percentile_natuser_psat_math_section: str | None = None
    percentile_natuser_psat_math_test: str | None = None
    percentile_natuser_psat_probslv_data: str | None = None
    percentile_natuser_psat_reading: str | None = None
    percentile_natuser_psat_sci_cross: str | None = None
    percentile_natuser_psat_total: str | None = None
    percentile_natuser_psat_words_context: str | None = None
    percentile_natuser_psat_writ_lang: str | None = None
    percentile_state_math: str | None = None
    percentile_state_rw: str | None = None
    percentile_state_total: str | None = None
    race_eth_africanamerican: str | None = None
    race_eth_asian: str | None = None
    race_eth_cuban: str | None = None
    race_eth_hawaiian_pi: str | None = None
    race_eth_hisp_lat: str | None = None
    race_eth_indian_alaskan: str | None = None
    race_eth_mexican: str | None = None
    race_eth_non_hisp_lat: str | None = None
    race_eth_other: str | None = None
    race_eth_puertorican: str | None = None
    race_eth_white: str | None = None
    reading_ques_correct: str | None = None
    reading_ques_incorrect: str | None = None
    reading_ques_omit: str | None = None
    report_date: str | None = None
    saa: str | None = None
    sdq_date: str | None = None
    sdq_gpa: str | None = None
    secondary_id: str | None = None
    selection_index: str | None = None
    state_student_id: str | None = None
    student_search_service: str | None = None
    writlang_ques_correct: str | None = None
    writlang_ques_incorrect: str | None = None
    writlang_ques_omit: str | None = None
    yrs_9to12: str | None = None

    math_cmc_ques_ans1: str | None = None
    math_cmc_ques_ans10: str | None = None
    math_cmc_ques_ans11: str | None = None
    math_cmc_ques_ans12: str | None = None
    math_cmc_ques_ans13: str | None = None
    math_cmc_ques_ans14: str | None = None
    math_cmc_ques_ans15: str | None = None
    math_cmc_ques_ans16: str | None = None
    math_cmc_ques_ans17: str | None = None
    math_cmc_ques_ans18: str | None = None
    math_cmc_ques_ans19: str | None = None
    math_cmc_ques_ans2: str | None = None
    math_cmc_ques_ans20: str | None = None
    math_cmc_ques_ans21: str | None = None
    math_cmc_ques_ans22: str | None = None
    math_cmc_ques_ans23: str | None = None
    math_cmc_ques_ans24: str | None = None
    math_cmc_ques_ans25: str | None = None
    math_cmc_ques_ans26: str | None = None
    math_cmc_ques_ans27: str | None = None
    math_cmc_ques_ans3: str | None = None
    math_cmc_ques_ans4: str | None = None
    math_cmc_ques_ans5: str | None = None
    math_cmc_ques_ans6: str | None = None
    math_cmc_ques_ans7: str | None = None
    math_cmc_ques_ans8: str | None = None
    math_cmc_ques_ans9: str | None = None
    math_cpr_ques_ans1: str | None = None
    math_cpr_ques_ans2: str | None = None
    math_cpr_ques_ans3: str | None = None
    math_cpr_ques_ans4: str | None = None
    math_ncmc_ques_ans1: str | None = None
    math_ncmc_ques_ans10: str | None = None
    math_ncmc_ques_ans11: str | None = None
    math_ncmc_ques_ans12: str | None = None
    math_ncmc_ques_ans13: str | None = None
    math_ncmc_ques_ans2: str | None = None
    math_ncmc_ques_ans3: str | None = None
    math_ncmc_ques_ans4: str | None = None
    math_ncmc_ques_ans5: str | None = None
    math_ncmc_ques_ans6: str | None = None
    math_ncmc_ques_ans7: str | None = None
    math_ncmc_ques_ans8: str | None = None
    math_ncmc_ques_ans9: str | None = None
    math_ncpr_ques_ans1: str | None = None
    math_ncpr_ques_ans2: str | None = None
    math_ncpr_ques_ans3: str | None = None
    math_ncpr_ques_ans4: str | None = None
    reading_ques_ans1: str | None = None
    reading_ques_ans10: str | None = None
    reading_ques_ans11: str | None = None
    reading_ques_ans12: str | None = None
    reading_ques_ans13: str | None = None
    reading_ques_ans14: str | None = None
    reading_ques_ans15: str | None = None
    reading_ques_ans16: str | None = None
    reading_ques_ans17: str | None = None
    reading_ques_ans18: str | None = None
    reading_ques_ans19: str | None = None
    reading_ques_ans2: str | None = None
    reading_ques_ans20: str | None = None
    reading_ques_ans21: str | None = None
    reading_ques_ans22: str | None = None
    reading_ques_ans23: str | None = None
    reading_ques_ans24: str | None = None
    reading_ques_ans25: str | None = None
    reading_ques_ans26: str | None = None
    reading_ques_ans27: str | None = None
    reading_ques_ans28: str | None = None
    reading_ques_ans29: str | None = None
    reading_ques_ans3: str | None = None
    reading_ques_ans30: str | None = None
    reading_ques_ans31: str | None = None
    reading_ques_ans32: str | None = None
    reading_ques_ans33: str | None = None
    reading_ques_ans34: str | None = None
    reading_ques_ans35: str | None = None
    reading_ques_ans36: str | None = None
    reading_ques_ans37: str | None = None
    reading_ques_ans38: str | None = None
    reading_ques_ans39: str | None = None
    reading_ques_ans4: str | None = None
    reading_ques_ans40: str | None = None
    reading_ques_ans41: str | None = None
    reading_ques_ans42: str | None = None
    reading_ques_ans43: str | None = None
    reading_ques_ans44: str | None = None
    reading_ques_ans45: str | None = None
    reading_ques_ans46: str | None = None
    reading_ques_ans47: str | None = None
    reading_ques_ans5: str | None = None
    reading_ques_ans6: str | None = None
    reading_ques_ans7: str | None = None
    reading_ques_ans8: str | None = None
    reading_ques_ans9: str | None = None
    writlang_ques_ans1: str | None = None
    writlang_ques_ans10: str | None = None
    writlang_ques_ans11: str | None = None
    writlang_ques_ans12: str | None = None
    writlang_ques_ans13: str | None = None
    writlang_ques_ans14: str | None = None
    writlang_ques_ans15: str | None = None
    writlang_ques_ans16: str | None = None
    writlang_ques_ans17: str | None = None
    writlang_ques_ans18: str | None = None
    writlang_ques_ans19: str | None = None
    writlang_ques_ans2: str | None = None
    writlang_ques_ans20: str | None = None
    writlang_ques_ans21: str | None = None
    writlang_ques_ans22: str | None = None
    writlang_ques_ans23: str | None = None
    writlang_ques_ans24: str | None = None
    writlang_ques_ans25: str | None = None
    writlang_ques_ans26: str | None = None
    writlang_ques_ans27: str | None = None
    writlang_ques_ans28: str | None = None
    writlang_ques_ans29: str | None = None
    writlang_ques_ans3: str | None = None
    writlang_ques_ans30: str | None = None
    writlang_ques_ans31: str | None = None
    writlang_ques_ans32: str | None = None
    writlang_ques_ans33: str | None = None
    writlang_ques_ans34: str | None = None
    writlang_ques_ans35: str | None = None
    writlang_ques_ans36: str | None = None
    writlang_ques_ans37: str | None = None
    writlang_ques_ans38: str | None = None
    writlang_ques_ans39: str | None = None
    writlang_ques_ans4: str | None = None
    writlang_ques_ans40: str | None = None
    writlang_ques_ans41: str | None = None
    writlang_ques_ans42: str | None = None
    writlang_ques_ans43: str | None = None
    writlang_ques_ans44: str | None = None
    writlang_ques_ans5: str | None = None
    writlang_ques_ans6: str | None = None
    writlang_ques_ans7: str | None = None
    writlang_ques_ans8: str | None = None
    writlang_ques_ans9: str | None = None

    filler: str | None = FILLER_FIELD


class AP(BaseModel):
    ai_code: str | None = None
    ai_country_code: str | None = None
    ai_institution_name: str | None = None
    ai_international_postal_code: str | None = None
    ai_province: str | None = None
    ai_state: str | None = None
    ai_street_address_1: str | None = None
    ai_street_address_2: str | None = None
    ai_street_address_3: str | None = None
    ai_zip_code: str | None = None
    ap_number_ap_id: str | None = None
    award_type_1: str | None = None
    award_type_2: str | None = None
    award_type_3: str | None = None
    award_type_4: str | None = None
    award_type_5: str | None = None
    award_type_6: str | None = None
    award_year_1: str | None = None
    award_year_2: str | None = None
    award_year_3: str | None = None
    award_year_4: str | None = None
    award_year_5: str | None = None
    award_year_6: str | None = None
    best_language: str | None = None
    college_code: str | None = None
    contact_name: str | None = None
    date_grades_released_to_college: str | None = None
    date_of_birth: str | None = None
    date_of_last_student_update: str | None = None
    date_of_this_report: str | None = None
    derived_aggregate_race_ethnicity_2016_and_forward: str | None = None
    di_country_code: str | None = None
    di_institution_name: str | None = None
    di_international_postal_code: str | None = None
    di_province: str | None = None
    di_state: str | None = None
    di_street_address_1: str | None = None
    di_street_address_2: str | None = None
    di_street_address_3: str | None = None
    di_zip_code: str | None = None
    ethnic_group_2015_and_prior: str | None = None
    first_name: str | None = None
    gender: str | None = None
    grade_level: str | None = None
    last_name: str | None = None
    middle_initial: str | None = None
    previous_ai_code_1: str | None = None
    previous_ai_code_2: str | None = None
    previous_ai_year_1: str | None = None
    previous_ai_year_2: str | None = None
    race_ethnicity_student_response_2016_and_forward: str | None = None
    school_id: str | None = None
    student_country_code: str | None = None
    student_identifier: str | None = None
    student_international_postal_code: str | None = None
    student_province: str | None = None
    student_state: str | None = None
    student_street_address_1: str | None = None
    student_street_address_2: str | None = None
    student_street_address_3: str | None = None
    student_zip_code: str | None = None

    # The same set of 6 fields (year, exam code, score, irregularity code(s), and
    # section code) repeats for the student’s 3rd through 30th most recent AP Exams, if
    # applicable.
    admin_year_01: str | None = None
    admin_year_02: str | None = None
    admin_year_03: str | None = None
    admin_year_04: str | None = None
    admin_year_05: str | None = None
    admin_year_06: str | None = None
    admin_year_07: str | None = None
    admin_year_08: str | None = None
    admin_year_09: str | None = None
    admin_year_10: str | None = None
    admin_year_11: str | None = None
    admin_year_12: str | None = None
    admin_year_13: str | None = None
    admin_year_14: str | None = None
    admin_year_15: str | None = None
    admin_year_16: str | None = None
    admin_year_17: str | None = None
    admin_year_18: str | None = None
    admin_year_19: str | None = None
    admin_year_20: str | None = None
    admin_year_21: str | None = None
    admin_year_22: str | None = None
    admin_year_23: str | None = None
    admin_year_24: str | None = None
    admin_year_25: str | None = None
    admin_year_26: str | None = None
    admin_year_27: str | None = None
    admin_year_28: str | None = None
    admin_year_29: str | None = None
    admin_year_30: str | None = None
    class_section_code_01: str | None = None
    class_section_code_02: str | None = None
    class_section_code_03: str | None = None
    class_section_code_04: str | None = None
    class_section_code_05: str | None = None
    class_section_code_06: str | None = None
    class_section_code_07: str | None = None
    class_section_code_08: str | None = None
    class_section_code_09: str | None = None
    class_section_code_10: str | None = None
    class_section_code_11: str | None = None
    class_section_code_12: str | None = None
    class_section_code_13: str | None = None
    class_section_code_14: str | None = None
    class_section_code_15: str | None = None
    class_section_code_16: str | None = None
    class_section_code_17: str | None = None
    class_section_code_18: str | None = None
    class_section_code_19: str | None = None
    class_section_code_20: str | None = None
    class_section_code_21: str | None = None
    class_section_code_22: str | None = None
    class_section_code_23: str | None = None
    class_section_code_24: str | None = None
    class_section_code_25: str | None = None
    class_section_code_26: str | None = None
    class_section_code_27: str | None = None
    class_section_code_28: str | None = None
    class_section_code_29: str | None = None
    class_section_code_30: str | None = None
    exam_code_01: str | None = None
    exam_code_02: str | None = None
    exam_code_03: str | None = None
    exam_code_04: str | None = None
    exam_code_05: str | None = None
    exam_code_06: str | None = None
    exam_code_07: str | None = None
    exam_code_08: str | None = None
    exam_code_09: str | None = None
    exam_code_10: str | None = None
    exam_code_11: str | None = None
    exam_code_12: str | None = None
    exam_code_13: str | None = None
    exam_code_14: str | None = None
    exam_code_15: str | None = None
    exam_code_16: str | None = None
    exam_code_17: str | None = None
    exam_code_18: str | None = None
    exam_code_19: str | None = None
    exam_code_20: str | None = None
    exam_code_21: str | None = None
    exam_code_22: str | None = None
    exam_code_23: str | None = None
    exam_code_24: str | None = None
    exam_code_25: str | None = None
    exam_code_26: str | None = None
    exam_code_27: str | None = None
    exam_code_28: str | None = None
    exam_code_29: str | None = None
    exam_code_30: str | None = None
    exam_grade_01: str | None = None
    exam_grade_02: str | None = None
    exam_grade_03: str | None = None
    exam_grade_04: str | None = None
    exam_grade_05: str | None = None
    exam_grade_06: str | None = None
    exam_grade_07: str | None = None
    exam_grade_08: str | None = None
    exam_grade_09: str | None = None
    exam_grade_10: str | None = None
    exam_grade_11: str | None = None
    exam_grade_12: str | None = None
    exam_grade_13: str | None = None
    exam_grade_14: str | None = None
    exam_grade_15: str | None = None
    exam_grade_16: str | None = None
    exam_grade_17: str | None = None
    exam_grade_18: str | None = None
    exam_grade_19: str | None = None
    exam_grade_20: str | None = None
    exam_grade_21: str | None = None
    exam_grade_22: str | None = None
    exam_grade_23: str | None = None
    exam_grade_24: str | None = None
    exam_grade_25: str | None = None
    exam_grade_26: str | None = None
    exam_grade_27: str | None = None
    exam_grade_28: str | None = None
    exam_grade_29: str | None = None
    exam_grade_30: str | None = None
    irregularity_code_1_01: str | None = None
    irregularity_code_1_02: str | None = None
    irregularity_code_1_03: str | None = None
    irregularity_code_1_04: str | None = None
    irregularity_code_1_05: str | None = None
    irregularity_code_1_06: str | None = None
    irregularity_code_1_07: str | None = None
    irregularity_code_1_08: str | None = None
    irregularity_code_1_09: str | None = None
    irregularity_code_1_10: str | None = None
    irregularity_code_1_11: str | None = None
    irregularity_code_1_12: str | None = None
    irregularity_code_1_13: str | None = None
    irregularity_code_1_14: str | None = None
    irregularity_code_1_15: str | None = None
    irregularity_code_1_16: str | None = None
    irregularity_code_1_17: str | None = None
    irregularity_code_1_18: str | None = None
    irregularity_code_1_19: str | None = None
    irregularity_code_1_20: str | None = None
    irregularity_code_1_21: str | None = None
    irregularity_code_1_22: str | None = None
    irregularity_code_1_23: str | None = None
    irregularity_code_1_24: str | None = None
    irregularity_code_1_25: str | None = None
    irregularity_code_1_26: str | None = None
    irregularity_code_1_27: str | None = None
    irregularity_code_1_28: str | None = None
    irregularity_code_1_29: str | None = None
    irregularity_code_1_30: str | None = None
    irregularity_code_2_01: str | None = None
    irregularity_code_2_02: str | None = None
    irregularity_code_2_03: str | None = None
    irregularity_code_2_04: str | None = None
    irregularity_code_2_05: str | None = None
    irregularity_code_2_06: str | None = None
    irregularity_code_2_07: str | None = None
    irregularity_code_2_08: str | None = None
    irregularity_code_2_09: str | None = None
    irregularity_code_2_10: str | None = None
    irregularity_code_2_11: str | None = None
    irregularity_code_2_12: str | None = None
    irregularity_code_2_13: str | None = None
    irregularity_code_2_14: str | None = None
    irregularity_code_2_15: str | None = None
    irregularity_code_2_16: str | None = None
    irregularity_code_2_17: str | None = None
    irregularity_code_2_18: str | None = None
    irregularity_code_2_19: str | None = None
    irregularity_code_2_20: str | None = None
    irregularity_code_2_21: str | None = None
    irregularity_code_2_22: str | None = None
    irregularity_code_2_23: str | None = None
    irregularity_code_2_24: str | None = None
    irregularity_code_2_25: str | None = None
    irregularity_code_2_26: str | None = None
    irregularity_code_2_27: str | None = None
    irregularity_code_2_28: str | None = None
    irregularity_code_2_29: str | None = None
    irregularity_code_2_30: str | None = None

    filler: str | None = FILLER_FIELD
