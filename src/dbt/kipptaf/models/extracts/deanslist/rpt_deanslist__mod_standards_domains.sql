with
    progress_report_region as (
        select assessment_id, progress_report_region,
        from
            {{ ref("stg_google_appsheet__illuminate_assessments_extension") }},
            unnest(split(regions_progress_report, ' , ')) as progress_report_region
    ),

    report_card_region as (
        select assessment_id, report_card_region,
        from
            {{ ref("stg_google_appsheet__illuminate_assessments_extension") }},
            unnest(split(regions_report_card, ' , ')) as report_card_region
    )

select
    'Progress Report' as report_type,

    ar.academic_year,
    ar.powerschool_student_number as student_number,
    ar.subject_area,
    ar.term_administered,

    null as standard_domain,

    round(avg(ar.percent_correct), 2) as avg_percent_correct,
    case
        when round(avg(ar.percent_correct), 2) >= 85
        then 'Exceeds Expectations'
        when round(avg(ar.percent_correct), 2) >= 70
        then 'Met Expectations'
        when round(avg(ar.percent_correct), 2) >= 50
        then 'Approaching Expectations'
        when round(avg(ar.percent_correct), 2) >= 30
        then 'Below Expectations'
        when round(avg(ar.percent_correct), 2) >= 0
        then 'Far Below Expectations'
    end as performance_level,
from {{ ref("int_assessments__response_rollup") }} as ar
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on ar.academic_year = co.academic_year
    and ar.powerschool_student_number = co.student_number
    and co.rn_year = 1
    and co.grade_level < 5
inner join
    progress_report_region as r
    on ar.assessment_id = r.assessment_id
    and co.region = r.progress_report_region
where ar.response_type = 'overall'
group by
    ar.academic_year,
    ar.powerschool_student_number,
    ar.subject_area,
    ar.term_administered

union all

select
    'Report Card' as report_type,

    ar.academic_year,
    ar.powerschool_student_number as student_number,
    ar.subject_area,
    ar.term_administered,

    sd.standard_domain,

    round(avg(ar.percent_correct), 2) as avg_percent_correct,
    case
        when round(avg(ar.percent_correct), 2) >= 85
        then 'Exceeds Expectations'
        when round(avg(ar.percent_correct), 2) >= 70
        then 'Met Expectations'
        when round(avg(ar.percent_correct), 2) >= 50
        then 'Approaching Expectations'
        when round(avg(ar.percent_correct), 2) >= 30
        then 'Below Expectations'
        when round(avg(ar.percent_correct), 2) >= 0
        then 'Far Below Expectations'
    end as performance_level,
from {{ ref("int_assessments__response_rollup") }} as ar
inner join
    {{ ref("stg_assessments__standard_domains") }} as sd
    on ar.response_type_code = sd.standard_code
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on ar.academic_year = co.academic_year
    and ar.powerschool_student_number = co.student_number
    and co.rn_year = 1
    and co.grade_level < 5
inner join
    report_card_region as r
    on ar.assessment_id = r.assessment_id
    and co.region = r.report_card_region
where ar.response_type = 'standard'
group by
    ar.academic_year,
    ar.powerschool_student_number,
    ar.subject_area,
    ar.term_administered,
    sd.standard_domain
