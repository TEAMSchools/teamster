from pydantic import BaseModel


class OutlierDetection(BaseModel):
    observer_employee_number: int | None = None
    academic_year: int | None = None
    form_term: str | None = None
    term_num: int | None = None
    etr1a: float | None = None
    etr1b: float | None = None
    etr2a: float | None = None
    etr2b: float | None = None
    etr2c: float | None = None
    etr2d: float | None = None
    etr3a: float | None = None
    etr3b: float | None = None
    etr3c: float | None = None
    etr3d: float | None = None
    etr4a: float | None = None
    etr4b: float | None = None
    etr4c: float | None = None
    etr4d: float | None = None
    etr4e: float | None = None
    etr4f: float | None = None
    etr5a: float | None = None
    etr5b: float | None = None
    etr5c: float | None = None
    so1: float | None = None
    so2: float | None = None
    so3: float | None = None
    so4: float | None = None
    so5: float | None = None
    so6: float | None = None
    so7: float | None = None
    so8: float | None = None
    overall_score: float | None = None
    is_iqr_outlier_current: bool | None = None
    cluster_current: int | None = None
    tree_outlier_current: int | None = None
    cluster_global: int | None = None
    is_iqr_outlier_global: bool | None = None
    tree_outlier_global: int | None = None
    pc1_global: float | None = None
    pc1_current: float | None = None
    pc2_global: float | None = None
    pc2_current: float | None = None
    pc1_variance_explained_current: float | None = None
    pc1_variance_explained_global: float | None = None
    pc2_variance_explained_current: float | None = None
    pc2_variance_explained_global: float | None = None


class ObservationDetail(BaseModel):
    academic_year: int | None = None
    employee_number: int | None = None
    etr_score: float | None = None
    form_long_name: str | None = None
    form_term: str | None = None
    form_type: str | None = None
    glows: str | None = None
    grows: str | None = None
    measurement_name: str | None = None
    observation_id: str | None = None
    observed_at: str | None = None
    observer_employee_number: int | None = None
    overall_score: float | None = None
    rn_submission: int | None = None
    row_score_value: float | None = None
    rubric_id: str | None = None
    score_measurement_id: str | None = None
    score_measurement_shortname: str | None = None
    score_measurement_type: str | None = None
    so_score: float | None = None
    teacher_id: str | None = None
    text_box: str | None = None
