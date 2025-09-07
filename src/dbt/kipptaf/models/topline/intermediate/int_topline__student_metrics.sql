/* K-8 Reading & Math */
select
    'K-8 Reading and Math' as layer,
    'Formative Assessments' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    discipline,

    null as numerator,
    null as denominator,
    is_mastery_running_int as metric_value,
from {{ ref("int_topline__formative_assessment_weekly") }}

union all

select
    'K-8 Reading and Math' as layer,
    'DIBELS PM Mastery' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    'ELA' as discipline,

    null as numerator,
    null as denominator,
    met_pm_round_overall_criteria as metric_value,
from {{ ref("int_topline__dibels_pm_weekly") }}

union all

select
    'K-8 Reading and Math' as layer,
    'DIBELS PM Fidelity' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    'ELA' as discipline,

    null as numerator,
    null as denominator,
    completed_test_round_int as metric_value,
from {{ ref("int_topline__dibels_pm_weekly") }}

union all

select
    'K-8 Reading and Math' as layer,
    'i-Ready Diagnostic' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    discipline,

    null as numerator,
    null as denominator,
    is_proficient as metric_value,
from {{ ref("int_topline__iready_diagnostic_weekly") }}

union all

select
    'K-8 Reading and Math' as layer,
    'i-Ready Lessons' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    discipline,

    null as numerator,
    null as denominator,
    n_lessons_passed_week as metric_value,
from {{ ref("int_topline__iready_lessons_weekly") }}

union all

select
    'K-8 Reading and Math' as layer,
    'Star Diagnostic' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    discipline,

    null as numerator,
    null as denominator,
    is_state_benchmark_proficient_int as metric_value,
from {{ ref("int_topline__star_assessment_weekly") }}

union all

select
    'K-8 Reading and Math' as layer,
    'State Assessments' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    discipline,

    null as numerator,
    null as denominator,
    is_proficient_int as metric_value,
from {{ ref("int_topline__state_assessments_weekly") }}

union all

/* Attendance & Enrollment */
select
    'Attendance and Enrollment' as layer,
    'Successful Contacts' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    null as discipline,

    successful_comms_sum_running as numerator,
    required_comms_count_running as denominator,
    safe_divide(
        successful_comms_sum_running, required_comms_count_running
    ) as metric_value,
from {{ ref("int_topline__attendance_contacts_weekly") }}

union all

select
    'Attendance and Enrollment' as layer,
    'Chronic Absenteeism Interventions' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    null as discipline,

    successful_call_count as numerator,
    total_anticipated_calls as denominator,
    pct_interventions_complete as metric_value,
from {{ ref("int_topline__attendance_interventions_weekly") }}

union all

select
    'Attendance and Enrollment' as layer,
    'ADA' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    null as discipline,

    attendance_value_sum_running as numerator,
    membership_value_sum_running as denominator,
    ada_running as metric_value,
from {{ ref("int_topline__ada_running_weekly") }}

union all

/* GPA & ACT/SAT */
select
    'GPA, ACT, SAT' as layer,
    'Highest SAT' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    null as discipline,

    null as numerator,
    null as denominator,
    score as metric_value,
from {{ ref("int_topline__college_entrance_exams_weekly") }}

union all

select
    'GPA, ACT, SAT' as layer,
    'Projected Unweighted Cumulative GPA' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    null as discipline,

    null as numerator,
    null as denominator,
    cumulative_y1_gpa_projected_unweighted as metric_value,
from {{ ref("int_topline__gpa_cumulative_weekly") }}

union all

/* Student & Family Experience */
select
    'Student and Family Experience' as layer,
    'School Community Diagnostic' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    null as discipline,

    null as numerator,
    null as denominator,
    average_rating as metric_value,
from {{ ref("int_topline__school_community_diagnostic_weekly") }}

union all

select
    'Student and Family Experience' as layer,
    'Suspensions' as indicator,
    student_number,
    academic_year,
    week_start_monday as term,
    null as discipline,

    null as numerator,
    null as denominator,
    is_suspended_y1_all_running as metric_value,
from {{ ref("int_topline__suspension_weekly") }}
