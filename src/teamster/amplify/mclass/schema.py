from pydantic import BaseModel


class DYDModel(BaseModel):
    account_name: str | None = None
    alternate_assessment: str | None = None
    approved_accommodations: str | None = None
    assessing_teacher_name: str | None = None
    assessment_edition: str | None = None
    assessment: str | None = None
    classed: str | None = None
    client_date: str | None = None
    date_of_birth: str | None = None
    disability: str | None = None
    district_name: str | None = None
    district_primary_id: str | None = None
    economically_disadvantaged: str | None = None
    ell_status: str | None = None
    english_proficiency: str | None = None
    enrollment_date: str | None = None
    external_program: str | None = None
    gender: str | None = None
    home_language: str | None = None
    internal_program: str | None = None
    meal_status: str | None = None
    migrant: str | None = None
    municipality_name: str | None = None
    municipality_primary_id: str | None = None
    official_teacher_name: str | None = None
    primary_id_student_number: float | None = None
    primary_school_id: str | None = None
    race: str | None = None
    reporting_class_id: str | None = None
    reporting_class_name: str | None = None
    school_name: str | None = None
    school_year: str | None = None
    secondary_school_id: str | None = None
    section_504: str | None = None
    special_education: str | None = None
    specific_disability: str | None = None
    state: str | None = None
    student_first_name: str | None = None
    student_id_district_id: float | None = None
    student_id_state_id: str | None = None
    student_last_name: str | None = None
    student_middle_name: str | None = None
    student_primary_id: int | None = None
    sync_date: str | None = None
    title_1: str | None = None

    enrollment_grade: str | int | None = None
    assessing_teacher_staff_id: str | float | None = None
    assessment_grade: str | int | None = None
    official_teacher_staff_id: int | str | None = None
    primary_id_student_id_district_id: int | float | None = None


class BenchmarkStudentSummary(DYDModel):
    administration_type: str | None = None
    benchmark_period: str | None = None
    composite_level: str | None = None
    composite_national_norm_percentile: float | None = None
    composite_semester_growth: str | None = None
    composite_year_growth: str | None = None
    correct_responses_maze_score: float | None = None
    decoding_nwf_wrc_level: str | None = None
    decoding_nwf_wrc_national_norm_percentile: str | None = None
    decoding_nwf_wrc_score: float | None = None
    decoding_nwf_wrc_semester_growth: str | None = None
    decoding_nwf_wrc_year_growth: str | None = None
    dibels_composite_score_lexile: str | None = None
    error_rate_orf_score: float | None = None
    incorrect_responses_maze_score: float | None = None
    letter_names_lnf_level: str | None = None
    letter_names_lnf_score: float | None = None
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
    ran_level: str | None = None
    ran_score: float | None = None
    reading_accuracy_orf_accu_level: str | None = None
    reading_accuracy_orf_accu_score: float | None = None
    reading_accuracy_orf_accu_semester_growth: str | None = None
    reading_accuracy_orf_accu_year_growth: str | None = None
    reading_comprehension_maze_level: str | None = None
    reading_comprehension_maze_national_norm_percentile: float | None = None
    reading_comprehension_maze_score: float | None = None
    reading_comprehension_maze_semester_growth: str | None = None
    reading_comprehension_maze_year_growth: str | None = None
    reading_fluency_orf_level: str | None = None
    reading_fluency_orf_score: float | None = None
    reading_fluency_orf_semester_growth: str | None = None
    reading_fluency_orf_year_growth: str | None = None
    risk_indicator_level: str | None = None
    spelling_level: str | None = None
    spelling_score: float | None = None
    vocabulary_level: str | None = None
    vocabulary_score: float | None = None
    word_reading_wrf_level: str | None = None
    word_reading_wrf_national_norm_percentile: str | None = None
    word_reading_wrf_score: float | None = None
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
