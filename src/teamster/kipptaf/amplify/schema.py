import json

from py_avro_schema import generate
from pydantic import BaseModel


class DYDModel(BaseModel):
    account_name: str
    alternate_assessment: str
    approved_accommodations: str
    assessing_teacher_name: str
    assessment_edition: str
    assessment_grade: str
    assessment: str
    classed: str
    disability: str
    district_name: str
    district_primary_id: str
    economically_disadvantaged: str
    ell_status: str
    english_proficiency: str
    enrollment_grade: str
    external_program: str
    gender: str
    home_language: str
    internal_program: str
    meal_status: str
    migrant: str
    municipality_name: str
    municipality_primary_id: str
    official_teacher_name: str
    primary_id_student_number: float
    primary_school_id: str
    race: str
    reporting_class_id: str
    reporting_class_name: str
    school_name: str
    school_year: str
    secondary_school_id: str
    section_504: str
    special_education: str
    specific_disability: str
    state: str
    student_first_name: str
    student_id_district_id: float
    student_id_state_id: str
    student_last_name: str
    student_middle_name: str
    student_primary_id: int
    title_1: str
    client_date: str
    date_of_birth: str
    enrollment_date: str
    sync_date: str

    assessing_teacher_staff_id: str | float | None = None
    official_teacher_staff_id: int | str | None = None
    primary_id_student_id_district_id: int | float | None = None


class BenchmarkStudentSummary(DYDModel):
    administration_type: str | None = None
    benchmark_period: str | None = None
    composite_level: str | None = None
    composite_semester_growth: str | None = None
    composite_year_growth: str | None = None
    decoding_nwf_wrc_level: str | None = None
    decoding_nwf_wrc_score: float | None = None
    error_rate_orf_score: float | None = None
    letter_names_lnf_level: str | None = None
    letter_names_lnf_score: float | None = None
    ran_level: str | None = None
    ran_score: float | None = None
    reading_fluency_orf_level: str | None = None
    reading_fluency_orf_score: float | None = None
    risk_indicator_level: str | None = None
    spelling_level: str | None = None
    spelling_score: float | None = None
    vocabulary_level: str | None = None
    vocabulary_score: float | None = None
    word_reading_wrf_level: str | None = None
    word_reading_wrf_score: float | None = None
    composite_national_norm_percentile: float | None = None
    correct_responses_maze_score: float | None = None
    decoding_nwf_wrc_national_norm_percentile: str | None = None
    decoding_nwf_wrc_semester_growth: str | None = None
    decoding_nwf_wrc_year_growth: str | None = None
    dibels_composite_score_lexile: str | None = None
    incorrect_responses_maze_score: float | None = None
    letter_names_lnf_semester_growth: str | None = None
    letter_names_lnf_year_growth: str | None = None
    letter_sounds_nwf_cls_level: str | None = None
    letter_sounds_nwf_cls_national_norm_percentile: str | None = None
    letter_sounds_nwf_cls_score: float | None = None
    letter_sounds_nwf_cls_semester_growth: str | None = None
    letter_sounds_nwf_cls_year_growth: str | None = None
    phonemic_awareness_psf_level: str | None = None
    phonemic_awareness_psf_score: float | None = None
    phonemic_awareness_psf_semester_growth: str | None = None
    phonemic_awareness_psf_year_growth: str | None = None
    reading_accuracy_orf_accu_level: str | None = None
    reading_accuracy_orf_accu_score: float | None = None
    reading_accuracy_orf_accu_semester_growth: str | None = None
    reading_accuracy_orf_accu_year_growth: str | None = None
    reading_comprehension_maze_level: str | None = None
    reading_comprehension_maze_national_norm_percentile: float | None = None
    reading_comprehension_maze_score: float | None = None
    reading_comprehension_maze_semester_growth: str | None = None
    reading_comprehension_maze_year_growth: str | None = None
    reading_fluency_orf_semester_growth: str | None = None
    reading_fluency_orf_year_growth: str | None = None
    word_reading_wrf_national_norm_percentile: str | None = None
    word_reading_wrf_semester_growth: str | None = None
    word_reading_wrf_year_growth: str | None = None

    composite_score: int | float | None = None
    letter_names_lnf_national_norm_percentile: str | float | None = None
    phonemic_awareness_psf_national_norm_percentile: str | float | None = None
    reading_accuracy_orf_accu_national_norm_percentile: float | str | None = None
    reading_fluency_orf_national_norm_percentile: float | str | None = None


class PMStudentSummary(DYDModel):
    measure: str | None = None
    pm_period: str | None = None
    probe_number: int | None = None
    total_number_of_probes: int | None = None

    score_change: str | float | None = None
    score: int | float | None = None


ASSET_FIELDS = {
    "benchmark_student_summary": json.loads(
        generate(py_type=BenchmarkStudentSummary, namespace="benchmark_student_summary")
    ),
    "pm_student_summary": json.loads(
        generate(py_type=PMStudentSummary, namespace="pm_student_summary")
    ),
}
