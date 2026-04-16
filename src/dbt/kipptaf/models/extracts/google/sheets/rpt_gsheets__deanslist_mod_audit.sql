with
    progress_report_region as (
        select iae.assessment_id, progress_report_region,
        from
            {{ ref("stg_google_appsheet__illuminate_assessments_extension") }} as iae
        cross join
            unnest(split(iae.regions_progress_report, ' , ')) as progress_report_region
    ),

    report_card_region as (
        select iae.assessment_id, report_card_region,
        from
            {{ ref("stg_google_appsheet__illuminate_assessments_extension") }} as iae
        cross join
            unnest(split(iae.regions_report_card, ' , ')) as report_card_region
    ),

    mod_assessment as (
        select
            ar.powerschool_student_number as student_number,
            ar.academic_year,
            ar.assessment_id,
            ar.title,
            ar.scope,
            ar.subject_area,
            ar.term_administered,
            ar.response_type,
            ar.response_type_description,
            ar.percent_correct,
            ar.performance_band_label,
            ar.is_internal_assessment,

            co.grade_level,
            co.region,

            cast(null as string) as standard_domain,

            'mod_assessment' as source_model,
            cast(null as string) as report_type,
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
    ),

    mod_standards as (
        select
            ar.powerschool_student_number as student_number,
            ar.academic_year,
            ar.assessment_id,
            ar.title,
            ar.scope,
            ar.subject_area,
            ar.term_administered,
            ar.response_type,
            ar.response_type_description,
            ar.percent_correct,
            ar.performance_band_label,
            ar.is_internal_assessment,

            cast(null as int64) as grade_level,
            cast(null as string) as region,
            cast(null as string) as standard_domain,

            'mod_standards' as source_model,
            cast(null as string) as report_type,
        from {{ ref("int_assessments__response_rollup") }} as ar
        where
            ar.is_internal_assessment
            and ar.response_type = 'group'
            and ar.academic_year = {{ var("current_academic_year") }}
            and ar.subject_area in ('Text Study', 'Mathematics', 'Writing')
    ),

    mod_standards_domains as (
        select
            ar.powerschool_student_number as student_number,
            ar.academic_year,
            ar.assessment_id,
            ar.title,
            ar.scope,
            ar.subject_area,
            ar.term_administered,
            ar.response_type,
            ar.response_type_description,
            ar.percent_correct,
            ar.performance_band_label,
            ar.is_internal_assessment,

            co.grade_level,
            co.region,

            cast(null as string) as standard_domain,

            'mod_standards_domains' as source_model,
            'Progress Report' as report_type,
        from {{ ref("int_assessments__response_rollup") }} as ar
        inner join
            {{ ref("int_extracts__student_enrollments") }} as co
            on ar.academic_year = co.academic_year
            and ar.powerschool_student_number = co.student_number
            and co.rn_year = 1
            and co.grade_level < 5
        inner join
            progress_report_region as prr
            on ar.assessment_id = prr.assessment_id
            and co.region = prr.progress_report_region
        where
            ar.response_type = 'overall'
            and ar.academic_year = {{ var("current_academic_year") }}

        union all

        select
            ar.powerschool_student_number as student_number,
            ar.academic_year,
            ar.assessment_id,
            ar.title,
            ar.scope,
            ar.subject_area,
            ar.term_administered,
            ar.response_type,
            ar.response_type_description,
            ar.percent_correct,
            ar.performance_band_label,
            ar.is_internal_assessment,

            co.grade_level,
            co.region,

            sd.standard_domain,

            'mod_standards_domains' as source_model,
            'Report Card' as report_type,
        from {{ ref("int_assessments__response_rollup") }} as ar
        inner join
            {{ ref("stg_google_sheets__assessments__standard_domains") }} as sd
            on ar.response_type_code = sd.standard_code
        inner join
            {{ ref("int_extracts__student_enrollments") }} as co
            on ar.academic_year = co.academic_year
            and ar.powerschool_student_number = co.student_number
            and co.rn_year = 1
            and co.grade_level < 5
        inner join
            report_card_region as rcr
            on ar.assessment_id = rcr.assessment_id
            and co.region = rcr.report_card_region
        where
            ar.response_type = 'standard'
            and ar.academic_year = {{ var("current_academic_year") }}
    ),

    all_responses as (
        select * from mod_assessment
        union all
        select * from mod_standards
        union all
        select * from mod_standards_domains
    )

select
    source_model,
    report_type,
    student_number,
    academic_year,
    grade_level,
    region,
    assessment_id,
    title,
    scope,
    subject_area,
    term_administered,
    response_type,
    response_type_description,
    standard_domain,
    percent_correct,
    performance_band_label,
    is_internal_assessment,

    round(
        avg(percent_correct) over (
            partition by
                source_model,
                report_type,
                student_number,
                academic_year,
                subject_area,
                term_administered,
                if(source_model = 'mod_standards', response_type, null),
                if(source_model = 'mod_standards', response_type_description, null),
                if(
                    source_model = 'mod_standards_domains'
                    and report_type = 'Report Card',
                    standard_domain,
                    null
                )
        ),
        0
    ) as computed_avg_pct_correct,
from all_responses
