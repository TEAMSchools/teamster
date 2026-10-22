with
    benchmark_union as (
        select
            _dbt_source_project,
            student_number,
            scale_score,
            is_proficient_int,
            is_approaching_int,
            is_below_int,

            performance_level as `level`,

            scale_score as scale_score_state,
            is_proficient_int as is_proficient_int_state,
            cast(null as int64) as scale_score_iready,

            case
                when score_source = 'state_nj'
                then assessment_name
                when assessment_name = 'EOC'
                then 'Algebra I EOC'
                else concat('FAST ', administration_period)
            end as assessment_type,

            if(illuminate_subject_area = 'Text Study', 'Reading', 'Math') as `subject`,

            -- grade 3 FAST reads PM1 of the same year, not PM3 of the prior year
            academic_year + if(
                score_source = 'state_fl' and administration_period = 'PM1', 0, 1
            ) as academic_year,

            case
                when score_source = 'state_nj'
                then 'njsla_prior_year'
                when assessment_name = 'EOC'
                then 'eoc_algebra_prior_year'
                when administration_period = 'PM1'
                then 'fast_pm1'
                else 'fast_pm3_prior_year'
            end as `source`,
        from {{ ref("int_assessments__state_scores") }}
        where
            student_number is not null
            and (
                (
                    score_source = 'state_nj'
                    and assessment_name = 'NJSLA'
                    and not (
                        grade_level_when_assessed = 8 and raw_subject like 'Algebra%'
                    )
                )
                or (
                    score_source = 'state_fl'
                    and assessment_name = 'FAST'
                    and scale_score is not null
                    and administration_period in ('PM1', 'PM3')
                )
                or (
                    score_source = 'state_fl'
                    and assessment_name = 'EOC'
                    and raw_subject = 'Algebra I'
                    and scale_score is not null
                )
            )

        union all

        select
            _dbt_source_project,
            student_display_id as student_number,
            unified_score as scale_score,

            if(state_benchmark_category_level < 4, 1, 0) as is_proficient_int,
            if(state_benchmark_category_level = 4, 1, 0) as is_approaching_int,
            if(state_benchmark_category_level = 5, 1, 0) as is_below_int,

            state_benchmark_category_level as `level`,

            unified_score as scale_score_state,
            if(state_benchmark_category_level < 4, 1, 0) as is_proficient_int_state,
            cast(null as int64) as scale_score_iready,

            'Star EOY' as assessment_type,

            if(star_discipline = 'ELA', 'Reading', star_discipline) as `subject`,

            academic_year + 1 as academic_year,

            'star_eoy_prior_year' as `source`,
        from {{ ref("stg_renlearn__star") }}
        where
            student_display_id is not null
            and rn_subject_round = 1
            and screening_period_window_name = 'Spring'

        union all

        select
            _dbt_source_project,
            student_display_id as student_number,
            unified_score as scale_score,

            if(district_benchmark_category_level = 1, 1, 0) as is_proficient_int,
            if(district_benchmark_category_level = 2, 1, 0) as is_approaching_int,
            if(district_benchmark_category_level >= 3, 1, 0) as is_below_int,

            district_benchmark_category_level as `level`,

            cast(null as numeric) as scale_score_state,
            cast(null as int64) as is_proficient_int_state,
            unified_score as scale_score_iready,

            'Star BOY' as assessment_type,

            if(star_discipline = 'ELA', 'Reading', star_discipline) as `subject`,

            academic_year,

            'star_boy' as `source`,
        from {{ ref("stg_renlearn__star") }}
        where
            student_display_id is not null
            and rn_subject_round = 1
            and screening_period_window_name = 'Fall'

        union all

        select
            _dbt_source_project,
            student_id as student_number,
            overall_scale_score + annual_typical_growth_measure as scale_score,

            if(projected_is_proficient_typical, 1, 0) as is_proficient_int,

            case
                when region = 'KIPP Miami' and projected_level_number_typical = 2
                then 1
                when region != 'KIPP Miami' and projected_level_number_typical = 3
                then 1
                else 0
            end as is_approaching_int,

            case
                when region = 'KIPP Miami' and projected_level_number_typical < 2
                then 1
                when region != 'KIPP Miami' and projected_level_number_typical < 3
                then 1
                else 0
            end as is_below_int,

            projected_level_number_typical as `level`,

            cast(null as numeric) as scale_score_state,
            cast(null as int64) as is_proficient_int_state,

            overall_scale_score + annual_typical_growth_measure as scale_score_iready,

            'i-Ready BOY' as assessment_type,

            `subject`,

            academic_year_int as academic_year,

            'iready_boy' as `source`,
        from {{ ref("int_assessments__iready_diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and projected_sublevel_number_typical is not null
            and student_grade_int between 3 and 8

        union all

        select
            _dbt_source_project,
            student_id as student_number,
            overall_scale_score + annual_typical_growth_measure as scale_score,

            if(level_number_with_typical >= 4, 1, 0) as is_proficient_int,
            if(level_number_with_typical = 3, 1, 0) as is_approaching_int,
            if(level_number_with_typical < 3, 1, 0) as is_below_int,

            level_number_with_typical as `level`,

            cast(null as numeric) as scale_score_state,
            cast(null as int64) as is_proficient_int_state,

            overall_scale_score + annual_typical_growth_measure as scale_score_iready,

            'i-Ready BOY' as assessment_type,

            `subject`,

            academic_year_int as academic_year,

            'iready_boy' as `source`,
        from {{ ref("int_assessments__iready_diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and sublevel_number_with_typical is not null
            and student_grade_int in (0, 1, 2, 9)
    ),

    -- each source counts only for the grades where the generator's ay2026
    -- config names it; the enrolled grade, not the test's grade, decides
    benchmark_graded as (
        select
            bu.*,

            case
                when bu.`source` = 'iready_boy'
                then 2
                when e.region != 'Miami' and bu.`source` = 'njsla_prior_year'
                then 0
                when
                    e.region = 'Miami'
                    and e.grade_level = 0
                    and bu.`source` = 'star_boy'
                then 0
                when
                    e.region = 'Miami'
                    and e.grade_level in (1, 2)
                    and bu.`source` = 'star_eoy_prior_year'
                then 0
                when
                    e.region = 'Miami'
                    and e.grade_level = 3
                    and bu.`source` = 'fast_pm1'
                then 0
                when
                    e.region = 'Miami'
                    and e.grade_level between 4 and 9
                    and bu.`source` = 'fast_pm3_prior_year'
                then 0
                when
                    e.region = 'Miami'
                    and e.grade_level = 9
                    and bu.`source` = 'eoc_algebra_prior_year'
                then 1
            end as priority,
        from benchmark_union as bu
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on bu.student_number = e.student_number
            and bu.academic_year = e.academic_year
            and bu._dbt_source_project = e._dbt_source_project
        where e.rn_year = 1
    ),

    benchmark_ranked as (
        select
            *,

            max(if(scale_score is not null, 1, 0)) over (
                partition by
                    _dbt_source_project, student_number, academic_year, `subject`
            ) as is_tested_int,

            first_value(scale_score_state ignore nulls) over w
            as scale_score_state_pick,

            first_value(is_proficient_int_state ignore nulls) over w
            as is_proficient_int_state_pick,

            first_value(scale_score_iready ignore nulls) over w
            as scale_score_iready_pick,

            row_number() over (
                partition by
                    _dbt_source_project, student_number, academic_year, `subject`
                order by priority asc, scale_score desc
            ) as rn_benchmark,
        from benchmark_graded
        where priority is not null
        window
            w as (
                partition by
                    _dbt_source_project, student_number, academic_year, `subject`
                order by priority asc, scale_score desc
                rows between unbounded preceding and unbounded following
            )
    )

select
    _dbt_source_project,
    student_number,
    academic_year,
    `subject`,
    scale_score,
    is_proficient_int,
    is_approaching_int,
    is_below_int,
    is_tested_int,

    `level` as performance_level,
    assessment_type as benchmark_assessment_type,
    scale_score_state_pick as scale_score_state,
    is_proficient_int_state_pick as is_proficient_int_state,
    scale_score_iready_pick as scale_score_iready,
from benchmark_ranked
where rn_benchmark = 1
