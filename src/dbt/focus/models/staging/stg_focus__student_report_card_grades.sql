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
    -- live postings with a grade-type token (e.g. DT7181). safe_cast keeps only
    -- values that are already a plain id, so downstream joins to
    -- stg_focus__marking_periods compare plain columns; a prefixed value goes
    -- null rather than being decoded, since stripping a token cannot be done
    -- safely without knowing Focus's full token vocabulary — the trailing digit
    -- run of an unknown token could collide with a real id.
    -- TODO: decode the token from the raw dlt table once its vocabulary is
    -- known, so live postings recover their marking period.
    safe_cast(marking_period_id as int) as marking_period_id,
from {{ source("focus", "student_report_card_grades") }}
