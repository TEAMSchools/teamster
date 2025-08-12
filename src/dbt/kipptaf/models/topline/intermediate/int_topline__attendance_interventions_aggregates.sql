select
    student_number,
    academic_year,
    schoolid,

    sum(intervention_status_required_int) as successful_call_count,
    count(intervention_status_required_int) as total_anticipated_calls,
    avg(intervention_status_required_int) as pct_interventions_complete,
from {{ ref("int_topline__attendance_interventions") }}
group by student_number, academic_year, schoolid
