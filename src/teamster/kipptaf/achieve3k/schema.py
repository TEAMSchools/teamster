import json

import py_avro_schema
from pydantic import BaseModel


class Student(BaseModel):
    activities: float | None = None
    after_school_logins: float | None = None
    average_first_try_score: float | None = None
    average_weekly_activities: float | None = None
    college_and_career_readiness_current: str | None = None
    college_and_career_readiness_interim_test: str | None = None
    college_and_career_readiness_post_test: str | None = None
    college_and_career_readiness_pre_test: str | None = None
    current_lexile_level: float | None = None
    current_reading_level: float | None = None
    district_id: int | None = None
    district_school_id: str | None = None
    district_status: str | None = None
    district: str | None = None
    editions: str | None = None
    ell: str | None = None
    expected_lexile_growth: str | None = None
    first_login: str | None = None
    grade: int | None = None
    interim_normal_curve_equivalent: float | None = None
    interim_percentile_rank: float | None = None
    interim_test_date: str | None = None
    interim_test_lexile: float | None = None
    interim_test_reading_level: float | None = None
    invalid_activities: float | None = None
    language_id: int | None = None
    language: str | None = None
    last_adjustment_date: str | None = None
    last_login: str | None = None
    manual_adjustments: str | None = None
    passing_activities: float | None = None
    post_test_date: str | None = None
    post_test_lexile: float | None = None
    post_test_normal_curve_equivalent: float | None = None
    post_test_percentile_rank: float | None = None
    post_test_reading_level: float | None = None
    pre_test_date: str | None = None
    pre_test_lexile: float | None = None
    pre_test_normal_curve_equivalent: float | None = None
    pre_test_percentile_rank: float | None = None
    pre_test_reading_level: float | None = None
    program_hours: float | None = None
    program: str | None = None
    purchasing_entity: str | None = None
    reading_connections_generate_questions: float | None = None
    reading_connections_setting_the_purpose: float | None = None
    reading_connections_summarization: float | None = None
    school_id: int | None = None
    school: str | None = None
    sped: str | None = None
    student_id: int | None = None
    student_name: str | None = None
    top_career_cluster: str | None = None
    top_career_name: str | None = None
    total_activities: float | None = None
    total_logins: float | None = None
    user_id: int | None = None
    writing_assignments: float | None = None


class students_record(Student):
    """helper classes for backwards compatibility"""


STUDENT_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=students_record,
        options=py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE,
    )
)
