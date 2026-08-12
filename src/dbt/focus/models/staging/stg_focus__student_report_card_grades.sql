select
    id,
    syear,
    school_id,
    student_id,
    grad_subject_id,
    course_num,
    course_title,
    grade_title,
    gpa_points,
    weighted_gpa_points,
    credits,
    credits_earned,
    affects_gpa,
    carries_credits,
    course_history,
    uuid,
    created_at,
    updated_at,

    custom_1 as course_flag_1,
    custom_2 as course_flag_2,
    custom_5 as district_number,
    custom_6 as school_number,
    custom_7 as grade_level,

    -- Focus stores this FK as a string here (int64 everywhere else) and prefixes
    -- live postings with a grade-type token (e.g. DT7181), so strip the token
    -- before casting: downstream joins to stg_focus__marking_periods then compare
    -- plain columns. TODO: the token itself is dropped; decode it from the raw
    -- dlt table if it turns out to distinguish grade types.
    cast(regexp_extract(marking_period_id, r'[0-9]+$') as int) as marking_period_id,
from {{ source("focus", "student_report_card_grades") }}
