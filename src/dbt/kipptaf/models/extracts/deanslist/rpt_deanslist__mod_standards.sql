with
    response_clean as (
        select
            powerschool_student_number,
            academic_year,
            term_administered,
            response_type_description,
            performance_band_set_id,
            percent_correct,
            if(subject_area = 'Writing', 'Text Study', subject_area) as subject_area,
            upper(left(response_type, 1)) as response_type,
        from {{ ref("int_assessments__response_rollup") }}
        where
            is_internal_assessment
            and response_type = 'group'
            and academic_year = {{ var("current_academic_year") }}
            and subject_area in ('Text Study', 'Mathematics', 'Writing')
    ),

    std_avg as (
        select
            powerschool_student_number,
            academic_year,
            subject_area,
            term_administered,
            response_type,
            response_type_description,
            performance_band_set_id,

            round(avg(percent_correct), 0) as avg_percent_correct,
        from response_clean
        group by
            powerschool_student_number,
            academic_year,
            subject_area,
            term_administered,
            response_type,
            response_type_description,
            performance_band_set_id
    )

select
    sa.powerschool_student_number as student_number,
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
    {{ ref("base_illuminate__performance_band_sets") }} as pbl
    on sa.performance_band_set_id = pbl.performance_band_set_id
    and sa.avg_percent_correct between pbl.minimum_value and pbl.maximum_value
