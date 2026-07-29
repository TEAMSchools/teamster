-- Staging columns plus their decoded custom-field labels. Drives from staging
-- and LEFT JOINs the pivot: BigQuery UNPIVOT drops entities whose unpivoted
-- columns are all null, so the pivot alone is not a complete entity spine.
select
    s.*,

    p.fefp_number_label,
    p.scheduling_method_label,
    p.facility_type_label,
    p.cert_licensure_qual_status_label,
    p.highly_qualified_label,
    p.reading_intervention_component_label,
    p.location_of_student_label,
    p.eoc_exam_term_label,
    p.basic_skills_exam_label,
from {{ ref("stg_focus__course_periods") }} as s
left join
    {{ ref("int_focus__course_periods__pivot") }} as p
    on s.course_period_id = p.course_period_id
