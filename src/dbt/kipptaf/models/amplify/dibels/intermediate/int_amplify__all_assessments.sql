with
    assessments_scores as (
        select
            bss.academic_year as mclass_academic_year,
            bss.student_primary_id as mclass_student_number,
            bss.assessment_grade as mclass_assessment_grade,
            bss.assessment_grade_int as mclass_assessment_grade_int,
            bss.benchmark_period as mclass_period,
            bss.client_date as mclass_client_date,
            bss.sync_date as mclass_sync_date,

            u.mclass_measure_standard,
            u.mclass_measure_standard_score,
            u.mclass_measure_standard_level,
            u.mclass_measure_standard_level_int,
            u.mclass_measure_percentile,
            u.mclass_measure_semester_growth,
            u.mclass_measure_year_growth,

            'Benchmark' as assessment_type,
            null as mclass_probe_number,
            null as mclass_total_number_of_probes,
            null as mclass_score_change,

            row_number() over (
                partition by u.surrogate_key, u.mclass_measure_standard
                order by u.mclass_measure_standard_level_int desc
            ) as rn_highest,

            row_number() over (
                partition by bss.academic_year, bss.student_primary_id
                order by bss.client_date
            ) as rn_distinct,
        from {{ ref("stg_amplify__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key
        where
            bss.academic_year >= {{ var("current_academic_year") - 1 }}
            and bss.enrollment_grade = bss.assessment_grade

        union all

        select
            academic_year as mclass_academic_year,
            student_id as mclass_student_number,

            cast(null as string) as mclass_assessment_grade,
            null as mclass_assessment_grade_int,

            mclass_period,
            `date` as mclass_client_date,
            `date` as mclass_sync_date,
            mclass_measure_standard,
            mclass_measure_standard_score,
            mclass_measure_standard_level,
            mclass_measure_standard_level_int,
            mclass_measure_percentile,

            cast(null as string) as mclass_measure_semester_growth,
            cast(null as string) as mclass_measure_year_growth,
            'Benchmark' as assessment_type,
            null as mclass_probe_number,
            null as mclass_total_number_of_probes,
            null as mclass_score_change,

            row_number() over (
                partition by surrogate_key, mclass_measure_standard
                order by class_measure_standard_level_int desc
            ) as rn_highest,

            row_number() over (
                partition by academic_year, student_id order by `date`
            ) as rn_distinct,
        from {{ ref("int_amplify__dibels_data_farming_unpivot") }}
        where
            mclass_measure_standard
            in ('Reading Fluency (ORF)', 'Reading Comprehension (Maze)', 'Composite')

        union all

        select
            academic_year as mclass_academic_year,
            student_primary_id as mclass_student_number,
            assessment_grade as mclass_assessment_grade,
            assessment_grade_int as mclass_assessment_grade_int,
            pm_period as mclass_period,
            client_date as mclass_client_date,
            sync_date as mclass_sync_date,
            measure as mclass_measure_standard,
            mclass_measure_standard_score,

            'NA' as mclass_measure_standard_level,

            null as mclass_measure_standard_level_int,
            null as mclass_measure_percentile,

            'NA' as mclass_measure_semester_growth,
            'NA' as mclass_measure_year_growth,
            'PM' as assessment_type,

            probe_number as mclass_probe_number,
            total_number_of_probes as mclass_total_number_of_probes,
            score_change as mclass_score_change,

            row_number() over (
                partition by surrogate_key, measure order by score desc
            ) as rn_highest,

            row_number() over (
                partition by academic_year, student_primary_id order by client_date
            ) as rn_distinct,
        from {{ ref("stg_amplify__pm_student_summary") }}
        where
            academic_year >= {{ var("current_academic_year") - 1 }}
            and enrollment_grade = assessment_grade
    ),

    composite_only as (
        select
            mclass_academic_year,
            mclass_student_number,
            mclass_period,
            mclass_measure_level,
        from assessments_scores
        where mclass_measure = 'Composite' and rn_highest = 1
    ),

    overall_composite_by_window as (
        select
            mclass_academic_year,
            mclass_student_number,

            coalesce(p.boy, 'No data') as boy,
            coalesce(p.moy, 'No data') as moy,
            coalesce(p.eoy, 'No data') as eoy,
        from
            composite_only pivot (
                max(mclass_measure_level) for mclass_period in ('BOY', 'MOY', 'EOY')
            ) as p
    ),

    probe_eligible_tag as (
        select
            s.mclass_academic_year,
            s.mclass_student_number,

            c.boy,
            c.moy,
            c.eoy,

            if(
                c.boy in ('Below Benchmark', 'Well Below Benchmark'), 'Yes', 'No'
            ) as boy_probe_eligible,

            if(
                c.moy in ('Below Benchmark', 'Well Below Benchmark'), 'Yes', 'No'
            ) as moy_probe_eligible,
        from assessments_scores as s
        left join
            overall_composite_by_window as c
            on s.mclass_academic_year = c.mclass_academic_year
            and s.mclass_student_number = c.mclass_student_number
        where s.rn_distinct = 1 and s.assessment_type = 'Benchmark'
    )

select
    s.mclass_academic_year,
    s.mclass_student_number,
    s.assessment_type,
    s.mclass_assessment_grade,
    s.mclass_assessment_grade_int,
    s.mclass_period,
    s.mclass_client_date,
    s.mclass_sync_date,
    s.mclass_measure,
    s.mclass_measure_score,
    s.mclass_measure_level,
    s.mclass_measure_level_int,
    s.mclass_measure_percentile,
    s.mclass_measure_semester_growth,
    s.mclass_measure_year_growth,
    s.mclass_probe_number,
    s.mclass_total_number_of_probes,
    s.mclass_score_change,

    p.boy_probe_eligible,
    p.moy_probe_eligible,
    p.boy as boy_composite,
    p.moy as moy_composite,
    p.eoy as eoy_composite,

    case
        when p.boy_probe_eligible = 'Yes' and s.mclass_period = 'BOY->MOY'
        then 'Yes'
        when p.moy_probe_eligible = 'Yes' and s.mclass_period = 'MOY->EOY'
        then 'Yes'
        when p.boy_probe_eligible = 'No' and s.mclass_period = 'BOY->MOY'
        then 'No'
        when p.moy_probe_eligible = 'No' and s.mclass_period = 'MOY->EOY'
        then 'No'
        else 'Not applicable'
    end as pm_probe_eligible,

    case
        when
            p.boy_probe_eligible = 'Yes'
            and s.mclass_period = 'BOY->MOY'
            and s.mclass_total_number_of_probes is not null
        then 'Yes'
        when
            p.moy_probe_eligible = 'Yes'
            and s.mclass_period = 'MOY->EOY'
            and s.mclass_total_number_of_probes is not null
        then 'Yes'
        when
            p.boy_probe_eligible = 'Yes'
            and s.mclass_period = 'BOY->MOY'
            and s.mclass_total_number_of_probes is null
        then 'No'
        when
            p.moy_probe_eligible = 'Yes'
            and s.mclass_period = 'MOY->EOY'
            and s.mclass_total_number_of_probes is null
        then 'No'
        else 'Not applicable'
    end as pm_probe_tested,
from assessments_scores as s
left join
    probe_eligible_tag as p
    on s.mclass_academic_year = p.mclass_academic_year
    and s.mclass_student_number = p.mclass_student_number
where s.rn_highest = 1
