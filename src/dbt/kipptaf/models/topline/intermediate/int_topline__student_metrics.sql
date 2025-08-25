select
    academic_year,
    region,
    school_level,
    schoolid,
    school,
    student_number,
    state_studentnumber,
    student_name,
    grade_level,
    gender,
    ethnicity,
    iep_status,
    is_504,
    lep_status,
    gifted_and_talented,
    entrydate,
    exitdate,
    enroll_status,

    null as `subject`,

    week_start_monday as term_name,
    week_start_monday as term_start,
    week_end_sunday as term_end,
    attendance_value_sum_running as numerator,
    membership_value_sum_running as denominator,
    ada_running as metric_value,

    'ADA Running' as metric_name,
    'Week' as term_type,
from {{ ref("int_topline__ada_running_weekly") }}

union all

select
    academic_year,
    region,
    school_level,
    schoolid,
    school,
    student_number,
    state_studentnumber,
    student_name,
    grade_level,
    gender,
    ethnicity,
    iep_status,
    is_504,
    lep_status,
    gifted_and_talented,
    entrydate,
    exitdate,
    enroll_status,

    iready_subject as `subject`,
    week_start_monday as term_name,
    week_start_monday as term_start,
    week_end_sunday as term_end,

    null as numerator,
    null as denominator,

    n_lessons_passed_week as metric_value,

    'i-Ready Lessons Passed' as metric_name,
    'Week' as term_type,
from {{ ref("int_topline__iready_lessons_weekly") }}

union all

select
    academic_year,
    region,
    school_level,
    schoolid,
    school,
    student_number,
    state_studentnumber,
    student_name,
    grade_level,
    gender,
    ethnicity,
    iep_status,
    is_504,
    lep_status,
    gifted_and_talented,
    entrydate,
    exitdate,
    enroll_status,

    iready_subject as `subject`,
    week_start_monday as term_name,
    week_start_monday as term_start,
    week_end_sunday as term_end,

    null as numerator,
    null as denominator,

    is_proficient as metric_value,

    'i-Ready Diagnostic Proficient' as metric_name,
    'Week' as term_type,
from {{ ref("int_topline__iready_diagnostic_weekly") }}
