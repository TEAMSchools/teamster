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
    district_name: str | None = None
    district_student_id: int | None = None
    ebrw_ccr_benchmark: str | None = None
    filler_1: str | None = None
    filler_2: str | None = None
    filler_3: str | None = None
    filler_4: str | None = None
    filler_5: str | None = None
    filler_6: str | None = None
    filler_7: str | None = None
    gender: str | None = None
    gpo: str | None = None
    grad_date: str | None = None
    hs_student: str | None = None
    latest_psat_date: str | None = None
    latest_psat_ebrw: int | None = None
    latest_psat_grade: int | None = None
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
    latest_psat_total: int | None = None
    latest_record_locator: str | None = None
    math_ccr_benchmark: str | None = None
    name_first: str | None = None
    name_last: str | None = None
    name_mi: str | None = None
    national_merit: str | None = None
    percentile_country_math: int | None = None
    percentile_country_rw: int | None = None
    percentile_country_total: int | None = None
    percentile_natrep_psat_ebrw: int | None = None
    percentile_natrep_psat_math_section: int | None = None
    percentile_natrep_psat_total: int | None = None
    percentile_natuser_psat_ebrw: int | None = None
    percentile_natuser_psat_math_section: int | None = None
    percentile_natuser_psat_total: int | None = None
    percentile_state_math: int | None = None
    percentile_state_rw: int | None = None
    percentile_state_total: int | None = None
    report_date: str | None = None
    secondary_id: float | None = None
    selection_index: int | None = None
    state_student_id: float | None = None
    yrs_9to12: str | None = None


PSAT_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=PSAT,
        options=(
            py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE
        ),
    )
)
