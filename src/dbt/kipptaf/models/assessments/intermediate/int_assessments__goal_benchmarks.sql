with
    state_test_union as (
        select
            _dbt_source_project,
            student_number,
            academic_year,
            scale_score,
            performance_level as `level`,
            is_proficient_int,
            is_approaching_int,
            is_below_int,
            source_system,
            illuminate_subject_area as `subject`,

            if(
                score_source = 'state_nj', assessment_name, 'FAST PM3'
            ) as assessment_type,

            -- grade 3 FAST reads PM1 of the same year, not PM3 of the prior year
            academic_year + if(
                score_source = 'state_fl' and administration_period = 'PM1', 0, 1
            ) as academic_year_plus,
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
                    and (
                        (administration_period = 'PM3' and test_grade != 3)
                        or (administration_period = 'PM1' and test_grade = 3)
                    )
                )
            )

        union all

        select
            _dbt_source_project,
            student_display_id as student_number,
            academic_year,
            unified_score as scale_score,
            state_benchmark_category_level as `level`,

            if(state_benchmark_category_level < 4, 1, 0) as is_proficient_int,
            if(state_benchmark_category_level = 4, 1, 0) as is_approaching_int,
            if(state_benchmark_category_level = 5, 1, 0) as is_below_int,

            cast(null as string) as source_system,

            if(star_discipline = 'ELA', 'Reading', star_discipline) as `subject`,

            'Star EOY' as assessment_type,

            academic_year + 1 as academic_year_plus,
        from {{ ref("stg_renlearn__star") }}
        where
            student_display_id is not null
            and rn_subject_round = 1
            and screening_period_window_name = 'Spring'
            and grade_level between 1 and 2
    ),

    state_test_resolved as (
        select
            _dbt_source_project,
            student_number,
            academic_year_plus,
            scale_score,
            `level`,
            assessment_type,
            is_proficient_int,
            is_approaching_int,
            is_below_int,

            case
                when source_system is null
                then `subject`
                when `subject` = 'Text Study'
                then 'Reading'
                else 'Math'
            end as `subject`,
        from state_test_union
    ),

    state_test_ranked as (
        select
            *,

            row_number() over (
                partition by
                    _dbt_source_project, student_number, academic_year_plus, `subject`
                order by scale_score desc
            ) as rn_state,
        from state_test_resolved
    ),

    state_test_picked as (select *, from state_test_ranked where rn_state = 1),

    iready_union as (
        select
            _dbt_source_project,
            student_id as student_number,
            academic_year_int as academic_year,
            `subject`,
            projected_level_number_typical as `level`,

            'i-Ready BOY' as assessment_type,

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
            academic_year_int as academic_year,
            `subject`,
            level_number_with_typical as `level`,

            'i-Ready BOY' as assessment_type,

            overall_scale_score + annual_typical_growth_measure as scale_score,

            if(level_number_with_typical >= 4, 1, 0) as is_proficient_int,
            if(level_number_with_typical = 3, 1, 0) as is_approaching_int,
            if(level_number_with_typical < 3, 1, 0) as is_below_int,
        from {{ ref("int_assessments__iready_diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and sublevel_number_with_typical is not null
            and student_grade_int in (0, 1, 2, 9)

        union all

        select
            _dbt_source_project,
            student_display_id as student_number,
            academic_year,

            if(star_discipline = 'ELA', 'Reading', star_discipline) as `subject`,

            district_benchmark_category_level as `level`,

            'Star BOY' as assessment_type,

            unified_score as scale_score,

            if(district_benchmark_category_level = 1, 1, 0) as is_proficient_int,
            if(district_benchmark_category_level = 2, 1, 0) as is_approaching_int,
            if(district_benchmark_category_level >= 3, 1, 0) as is_below_int,
        from {{ ref("stg_renlearn__star") }}
        where
            student_display_id is not null
            and rn_subject_round = 1
            and screening_period_window_name = 'Fall'
            and grade_level = 0
    ),

    iready_ranked as (
        select
            *,

            row_number() over (
                partition by
                    _dbt_source_project, student_number, academic_year, `subject`
                order by
                    case
                        assessment_type when 'Star BOY' then 0 when 'i-Ready BOY' then 1
                    end,
                    scale_score desc
            ) as rn_iready,
        from iready_union
    ),

    iready_picked as (select *, from iready_ranked where rn_iready = 1)

select
    st.scale_score as scale_score_state,
    st.is_proficient_int as is_proficient_int_state,

    ir.scale_score as scale_score_iready,

    coalesce(st._dbt_source_project, ir._dbt_source_project) as _dbt_source_project,
    coalesce(st.student_number, ir.student_number) as student_number,
    coalesce(st.academic_year_plus, ir.academic_year) as academic_year,
    coalesce(st.subject, ir.subject) as `subject`,
    coalesce(st.level, ir.level) as performance_level,
    coalesce(st.scale_score, ir.scale_score) as scale_score,
    coalesce(st.is_proficient_int, ir.is_proficient_int) as is_proficient_int,
    coalesce(st.is_approaching_int, ir.is_approaching_int) as is_approaching_int,
    coalesce(st.is_below_int, ir.is_below_int) as is_below_int,
    coalesce(st.assessment_type, ir.assessment_type) as benchmark_assessment_type,

    if(st.scale_score is not null or ir.scale_score is not null, 1, 0) as is_tested_int,
from state_test_picked as st
full join
    iready_picked as ir
    on st._dbt_source_project = ir._dbt_source_project
    and st.student_number = ir.student_number
    and st.academic_year_plus = ir.academic_year
    and st.subject = ir.subject
