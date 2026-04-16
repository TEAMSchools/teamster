with
    report_card_region as (
        select iae.assessment_id, report_card_region,
        from {{ ref("stg_google_appsheet__illuminate_assessments_extension") }} as iae
        cross join unnest(split(iae.regions_report_card, ' , ')) as report_card_region
    ),

    assessment_response_avg as (
        select
            ar.powerschool_student_number,
            ar.academic_year,
            ar.subject_area,
            ar.term_administered,

            replace(ar.term_administered, 'Q', 'QA') as module_num,

            min(ar.performance_band_set_id) as performance_band_set_id,

            round(avg(ar.percent_correct), 0) as avg_pct_correct,
        from {{ ref("int_assessments__response_rollup") }} as ar
        inner join
            {{ ref("int_extracts__student_enrollments") }} as co
            on ar.academic_year = co.academic_year
            and ar.powerschool_student_number = co.student_number
            and co.rn_year = 1
            and co.grade_level < 5
        left join
            report_card_region as rcr
            on ar.assessment_id = rcr.assessment_id
            and co.region = rcr.report_card_region
        where
            ar.response_type = 'overall'
            and ar.subject_area not in ('Text Study', 'Mathematics')
            and ar.academic_year = {{ var("current_academic_year") }}
            and ar.term_administered is not null
            and (ar.scope = 'Unit Assessment' or rcr.report_card_region is not null)
        group by
            ar.powerschool_student_number,
            ar.academic_year,
            ar.subject_area,
            ar.term_administered
    )

select
    ara.powerschool_student_number as student_number,
    ara.academic_year,
    ara.term_administered,
    ara.subject_area as subject_area_label,
    ara.module_num,
    ara.avg_pct_correct,

    pbl.label as proficiency_label,

    'ENRICHMENT' as subject_area,
    'UA' as scope,
    null as rn_unit,
from assessment_response_avg as ara
inner join
    {{ ref("int_illuminate__performance_band_sets") }} as pbl
    on ara.performance_band_set_id = pbl.performance_band_set_id
    and ara.avg_pct_correct between pbl.minimum_value and pbl.maximum_value
