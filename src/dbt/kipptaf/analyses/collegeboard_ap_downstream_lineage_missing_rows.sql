-- Downstream Lineage Verification -- Missing Rows
--
-- Run when collegeboard_ap_downstream_lineage_summary's unpivot_rows and
-- dashboard_scored_rows don't reconcile -- finds exactly which exam scores
-- are missing from the dashboard for that academic year.
--
-- Defaults to the network's current_academic_year -- override at compile
-- time for a different cycle: --vars '{current_academic_year: <year>}'.
select
    u.powerschool_student_number,
    u.exam_code_description,
    u.ps_ap_course_subject_code,
    u.ap_course_name,
from {{ ref("int_collegeboard__ap_unpivot") }} as u
left join
    {{ ref("rpt_tableau__ap_assessment_dashboard") }} as d
    on u.powerschool_student_number = d.student_number
    and u.ps_ap_course_subject_code = d.ps_ap_course_subject_code
    and d.academic_year = {{ var("current_academic_year") }}
    and d.test_name is not null
where u.academic_year = {{ var("current_academic_year") }} and d.student_number is null
