select
    id,
    syear,
    school_id,
    student_id,
    grad_subject_id,
    report_card_grade_id,
    grade_scale_id,
    course_period_id,
    course_num,
    course_title,
    grade_title,
    percent_grade,
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
    -- live postings with a grade-type token: DT is the running gradebook, DY is
    -- yesterday's grade, E is an exam (Focus SIS Level 1 Certification, Day 2).
    -- The decode strips any alpha prefix and casts the digit tail, rather than
    -- enumerating the tokens -- the vocabulary grew from 5 values to 8 in 5 days,
    -- so an enumeration would silently null the next token Focus adds. The token
    -- is kept as its own column because it is load-bearing for the grain:
    -- dropping it collapses 3,074 live-posted rows onto 1,542.
    regexp_extract(marking_period_id, r'^[A-Za-z]+') as grade_type_token,
    safe_cast(regexp_extract(marking_period_id, r'\d+$') as int) as marking_period_id,
from {{ source("focus", "student_report_card_grades") }}
