select
    s.powerschool_student_number as student_number,
    s.assessment_id,
    s.title,
    s.scope,
    s.subject_area,
    s.academic_year,
    s.administered_at,
    s.module_type,
    s.module_number,

    co.lastfirst,
    co.enroll_status,
    co.region,
    co.reporting_schoolid,
    co.grade_level,
    co.advisory_name as team,

    rta.name as term,

    asr.percent_correct,

    null as is_replacement,
from {{ ref("int_assessments__scaffold") }} as s
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on s.powerschool_student_number = co.student_number
    and s.academic_year = co.academic_year
    and co.rn_year = 1
    and co.enroll_status = 0
left join
    {{ ref("stg_reporting__terms") }} as rta
    on s.administered_at between rta.start_date and rta.end_date
    and s.powerschool_school_id = rta.school_id
    and rta.type = 'RT'
left join
    {{ ref("int_illuminate__agg_student_responses") }} as asr
    on s.student_assessment_id = asr.student_assessment_id
    and asr.response_type = 'overall'
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.is_internal_assessment
    and not s.is_replacement
