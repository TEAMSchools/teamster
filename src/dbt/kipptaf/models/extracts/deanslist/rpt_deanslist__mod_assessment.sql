/* Enrichment UA avgs */
with
    assessment_response_avg as (
        select
            powerschool_student_number,
            academic_year,
            subject_area,
            term_administered,
            replace(term_administered, 'Q', 'QA') as module_num,

            min(performance_band_set_id) as performance_band_set_id,
            round(avg(percent_correct), 0) as avg_pct_correct,
        from {{ ref("int_assessments__response_rollup") }}
        where
            scope = 'Unit Assessment'
            and subject_area not in ('Text Study', 'Mathematics')
            and academic_year = {{ var("current_fiscal_year") }}
        group by
            powerschool_student_number, academic_year, subject_area, term_administered
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
    {{ ref("base_illuminate__performance_band_sets") }} as pbl
    on ara.performance_band_set_id = pbl.performance_band_set_id
    and ara.avg_pct_correct between pbl.minimum_value and pbl.maximum_value
