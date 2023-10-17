select
    rr.powerschool_student_number as student_number,
    rr.assessment_id,
    rr.title,
    rr.term_administered as term,
    rr.administered_at,
    rr.subject_area,
    rr.scope,
    rr.module_type,
    rr.module_number,
    null as is_replacement,
    rr.percent_correct,

    co.lastfirst,
    co.enroll_status,
    co.region,
    co.reporting_schoolid,
    co.grade_level,
    co.advisory_name as team,
from {{ ref("int_assessments__response_rollup") }} as rr
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on rr.powerschool_student_number = co.student_number
    and rr.academic_year = co.academic_year
    and co.rn_year = 1
    and co.enroll_status = 0
where
    rr.is_internal_assessment and not rr.is_replacement and rr.response_type = 'overall'
