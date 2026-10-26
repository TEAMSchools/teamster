with
    response_clean as (
        select
            r.student_number,
            r.academic_year,
            r.term_administered,
            r.response_type_description,
            r.percent_correct,

            -- the assessment's set: Illuminate can tag a group with another
            pb.canonical_performance_band_set_id as performance_band_set_id,

            if(
                r.subject_area = 'Writing', 'Text Study', r.subject_area
            ) as subject_area,
            upper(left(r.response_type, 1)) as response_type,
        from {{ ref("int_assessments__response_rollup") }} as r
        inner join
            {{ ref("int_assessments__performance_bands") }} as pb
            on r.assessment_id = pb.assessment_id
            and pb.response_type = 'overall'
        where
            r.is_internal_assessment
            and r.response_type = 'group'
            and r.academic_year = {{ var("current_academic_year") }}
            and r.subject_area in ('Text Study', 'Mathematics', 'Writing')
    ),

    std_avg as (
        select
            student_number,
            academic_year,
            subject_area,
            term_administered,
            response_type,
            response_type_description,
            performance_band_set_id,

            round(avg(percent_correct), 0) as avg_percent_correct,
        from response_clean
        group by
            student_number,
            academic_year,
            subject_area,
            term_administered,
            response_type,
            response_type_description,
            performance_band_set_id
    )

select
    sa.student_number,
    sa.academic_year,
    sa.subject_area,
    sa.term_administered as term,
    sa.response_type,
    sa.response_type_description as standard_description,
    sa.avg_percent_correct as percent_correct,

    case
        pbl.label_number
        when 5
        then 'Advanced Mastery'
        when 4
        then 'Mastery'
        when 3
        then 'Approaching Mastery'
        when 2
        then 'Below Mastery'
        when 1
        then 'Far Below Mastery'
    end as standard_proficiency,
from std_avg as sa
inner join
    {{ ref("int_illuminate__performance_band_sets") }} as pbl
    on sa.performance_band_set_id = pbl.performance_band_set_id
    and sa.avg_percent_correct between pbl.minimum_value and pbl.maximum_value
