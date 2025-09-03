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
