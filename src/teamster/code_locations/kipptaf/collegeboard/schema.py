import json

import py_avro_schema
from pydantic import BaseModel


class PSAT(BaseModel):
    address_city: str | None = None
    address_country: str | None = None
    address_county: float | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    address_province: str | None = None
    address_state: str | None = None
    address_zip: float | None = None
    ai_code: int | None = None
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
    cb_id: int | None = None
    cohort_year: int | None = None
    derived_aggregate_race_eth: int | None = None
    district_name: str | None = None
    ebrw_ccr_benchmark: str | None = None
    email: str | None = None
    form_code: str | None = None
    gender: str | None = None
    gpo: str | None = None
    grad_date: str | None = None
    hs_student: str | None = None
    latest_access_cd: str | None = None
    latest_psat_adv_math: int | None = None
    latest_psat_comm_evidence: int | None = None
    latest_psat_date: str | None = None
    latest_psat_ebrw: int | None = None
    latest_psat_eng_convent: int | None = None
    latest_psat_expr_ideas: int | None = None
    latest_psat_heart_algebra: int | None = None
    latest_psat_hist_socst_cross: int | None = None
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
    latest_psat_math_section: int | None = None
    latest_psat_math_test: float | None = None
    latest_psat_probslv_data: int | None = None
    latest_psat_reading: int | None = None
    latest_psat_sci_cross: int | None = None
    latest_psat_total: int | None = None
    latest_psat_words_context: int | None = None
    latest_psat_writ_lang: int | None = None
    latest_record_locator: str | None = None
    latest_reg_num: str | None = None
    major_first: float | None = None
    math_c_ques_correct: int | None = None
    math_c_ques_incorrect: int | None = None
    math_c_ques_omit: int | None = None
    math_ccr_benchmark: str | None = None
    math_nc_ques_correct: int | None = None
    math_nc_ques_incorrect: int | None = None
    math_nc_ques_omit: int | None = None
    name_first: str | None = None
    name_last: str | None = None
    name_mi: str | None = None
    national_merit: str | None = None
    num_math_cmc_ques: int | None = None
    num_math_cpr_ques: int | None = None
    num_math_ncmc_ques: int | None = None
    num_math_ncpr_ques: int | None = None
    num_reading_ques: int | None = None
    num_writlang_ques: int | None = None
    percentile_country_math: int | None = None
    percentile_country_rw: int | None = None
    percentile_country_total: int | None = None
    percentile_natrep_psat_adv_math: int | None = None
    percentile_natrep_psat_comm_evidence: int | None = None
    percentile_natrep_psat_ebrw: int | None = None
    percentile_natrep_psat_eng_convent: int | None = None
    percentile_natrep_psat_expr_ideas: int | None = None
    percentile_natrep_psat_heart_algebra: int | None = None
    percentile_natrep_psat_hist_socst_cross: int | None = None
    percentile_natrep_psat_math_section: int | None = None
    percentile_natrep_psat_math_test: int | None = None
    percentile_natrep_psat_probslv_data: int | None = None
    percentile_natrep_psat_reading: int | None = None
    percentile_natrep_psat_sci_cross: int | None = None
    percentile_natrep_psat_total: int | None = None
    percentile_natrep_psat_words_context: int | None = None
    percentile_natrep_psat_writ_lang: int | None = None
    percentile_natuser_psat_adv_math: int | None = None
    percentile_natuser_psat_comm_evidence: int | None = None
    percentile_natuser_psat_ebrw: int | None = None
    percentile_natuser_psat_eng_convent: int | None = None
    percentile_natuser_psat_expr_ideas: int | None = None
    percentile_natuser_psat_heart_algebra: int | None = None
    percentile_natuser_psat_hist_socst_cross: int | None = None
    percentile_natuser_psat_math_section: int | None = None
    percentile_natuser_psat_math_test: int | None = None
    percentile_natuser_psat_probslv_data: int | None = None
    percentile_natuser_psat_reading: int | None = None
    percentile_natuser_psat_sci_cross: int | None = None
    percentile_natuser_psat_total: int | None = None
    percentile_natuser_psat_words_context: int | None = None
    percentile_natuser_psat_writ_lang: int | None = None
    percentile_state_math: int | None = None
    percentile_state_rw: int | None = None
    percentile_state_total: int | None = None
    reading_ques_correct: int | None = None
    reading_ques_incorrect: int | None = None
    reading_ques_omit: int | None = None
    report_date: str | None = None
    sdq_date: str | None = None
    sdq_gpa: float | None = None
    selection_index: int | None = None
    state_student_id: float | None = None
    student_search_service: str | None = None
    writlang_ques_correct: int | None = None
    writlang_ques_incorrect: int | None = None
    writlang_ques_omit: int | None = None
    yrs_9to12: str | None = None

    # best guess
    foreign_address: str | None = None
    homeschool: str | None = None
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
    saa: str | None = None

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

    # filler
    filler_1: str | None = None
    filler_10: str | None = None
    filler_11: str | None = None
    filler_12: str | None = None
    filler_13: str | None = None
    filler_14: str | None = None
    filler_15: str | None = None
    filler_16: str | None = None
    filler_17: str | None = None
    filler_18: str | None = None
    filler_19: str | None = None
    filler_2: str | None = None
    filler_20: str | None = None
    filler_21: str | None = None
    filler_22: str | None = None
    filler_23: str | None = None
    filler_24: str | None = None
    filler_25: str | None = None
    filler_26: str | None = None
    filler_27: str | None = None
    filler_28: str | None = None
    filler_29: str | None = None
    filler_3: str | None = None
    filler_30: str | None = None
    filler_31: str | None = None
    filler_32: str | None = None
    filler_33: str | None = None
    filler_34: str | None = None
    filler_35: str | None = None
    filler_36: str | None = None
    filler_37: str | None = None
    filler_38: str | None = None
    filler_39: str | None = None
    filler_4: str | None = None
    filler_40: str | None = None
    filler_41: str | None = None
    filler_42: str | None = None
    filler_43: str | None = None
    filler_44: str | None = None
    filler_45: str | None = None
    filler_46: str | None = None
    filler_47: str | None = None
    filler_48: str | None = None
    filler_49: str | None = None
    filler_5: str | None = None
    filler_50: str | None = None
    filler_51: str | None = None
    filler_52: str | None = None
    filler_53: str | None = None
    filler_54: str | None = None
    filler_55: str | None = None
    filler_56: str | None = None
    filler_57: str | None = None
    filler_58: str | None = None
    filler_59: str | None = None
    filler_6: str | None = None
    filler_60: str | None = None
    filler_61: str | None = None
    filler_62: str | None = None
    filler_63: str | None = None
    filler_64: str | None = None
    filler_65: str | None = None
    filler_66: str | None = None
    filler_67: str | None = None
    filler_68: str | None = None
    filler_69: str | None = None
    filler_7: str | None = None
    filler_8: str | None = None
    filler_9: str | None = None

    district_student_id: int | float | None = None
    latest_psat_grade: int | float | None = None
    secondary_id: int | float | None = None


PSAT_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=PSAT,
        options=(
            py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE
        ),
    )
)
