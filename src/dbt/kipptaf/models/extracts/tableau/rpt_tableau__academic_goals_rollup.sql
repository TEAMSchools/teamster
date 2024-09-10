with
    grade_bands as (
        select 'K-2' as band, grade_level,
        from unnest([0, 1, 2]) as grade_level
        union all
        select '3-8' as band, grade_level,
        from unnest([3, 4, 5, 6, 7, 8]) as grade_level
    ),

    goals as (
        select
            g.academic_year,
            g.region,

            gb.band,

            case
                when g.illuminate_subject_area = 'Text Study'
                then 'Reading'
                when g.illuminate_subject_area = 'Mathematics'
                then 'Math'
                else g.illuminate_subject_area
            end as subject,

            max(g.grade_band_goal) as grade_band_goal,
        from {{ ref("stg_assessments__academic_goals") }} as g
        inner join grade_bands as gb on g.grade_level = gb.grade_level
        group by all
    ),

    state_test_union as (
        select
            'NJSLA' as assessment_type,
            academic_year,
            academic_year + 1 as academic_year_plus,
            localstudentidentifier as student_number,
            case
                when subject like 'English%'
                then 'Reading'
                when subject like 'Algebra%' or subject in ('Mathematics', 'Geometry')
                then 'Math'
            end as subject,
            testscalescore as scale_score,
            testperformancelevel as level,
            if(testperformancelevel >= 4, 1, 0) as is_proficient_int,
            if(testperformancelevel = 3, 1, 0) as is_approaching_int,
            if(testperformancelevel < 3, 1, 0) as is_below_int,
        from {{ ref("stg_pearson__njsla") }}
        union all
        select
            'FAST' as assessment_type,
            f.academic_year,
            f.academic_year + 1 as academic_year_plus,
            s.student_number,
            case
                when f.assessment_subject = 'English Languate Arts'
                then 'Reading'
                else 'Math'
            end as subject,
            f.scale_score,
            f.achievement_level_int as level,
            if(f.achievement_level_int >= 3, 1, 0) as is_proficient_int,
            if(f.achievement_level_int = 2, 1, 0) as is_approaching_int,
            if(f.achievement_level_int < 2, 1, 0) as is_below_int,
        from {{ ref("stg_fldoe__fast") }} as f
        left join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on f.student_id = suf.fleid
            and {{ union_dataset_join_clause(left_alias="f", right_alias="suf") }}
        left join
            {{ ref("stg_powerschool__students") }} as s
            on suf.studentsdcid = s.dcid
            and {{ union_dataset_join_clause(left_alias="suf", right_alias="s") }}
        where f.scale_score is not null and f.administration_window = 'PM3'
    ),

    iready as (
        select
            'i-Ready BOY' as assessment_type,
            academic_year_int as academic_year,
            student_id as student_number,
            subject,
            projected_level_number_typical as level,
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
        from {{ ref("base_iready__diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and projected_sublevel_number_typical is not null
            and student_grade_int between 3 and 8

        union all

        select
            'i-Ready BOY' as assessment_type,
            academic_year_int as academic_year,
            student_id as student_number,
            subject,
            level_number_with_typical as level,

            overall_scale_score + annual_typical_growth_measure as scale_score,
            if(level_number_with_typical >= 4, 1, 0) as is_proficient_int,
            if(level_number_with_typical = 3, 1, 0) as is_approaching_int,
            if(level_number_with_typical < 3, 1, 0) as is_below_int,
        from {{ ref("base_iready__diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and sublevel_number_with_typical is not null
            and student_grade_int between 0 and 2
    ),

    roster as (
        select
            co.academic_year,
            co.student_number,
            co.lastfirst as student_name,
            co.region,
            co.grade_level,
            co.grade_level_prev,
            co.year_in_network,
            co.school_abbreviation as school,

            gb.band,

            subject,

            coalesce(
                st.assessment_type, ir.assessment_type, 'Untested'
            ) as benchmark_assessment_type,
            coalesce(st.level, ir.level) as performance_level,
            coalesce(st.scale_score, ir.scale_score) as scale_score,
            coalesce(st.is_proficient_int, ir.is_proficient_int) as is_proficient_int,
            coalesce(
                st.is_approaching_int, ir.is_approaching_int
            ) as is_approaching_int,
            coalesce(st.is_below_int, ir.is_below_int) as is_below_int,
            if(
                st.scale_score is not null or ir.scale_score is not null, 1, 0
            ) as is_tested_int,
            case
                when
                    coalesce(st.assessment_type, ir.assessment_type)
                    in ('NJSLA', 'FAST')
                    and co.grade_level > 3
                    and coalesce(st.is_approaching_int, ir.is_approaching_int) = 1
                then true
                when
                    coalesce(st.assessment_type, ir.assessment_type) = 'i-Ready'
                    and co.grade_level = 3
                    and coalesce(st.is_approaching_int, ir.is_approaching_int) = 1
                then true
                else false
            end as is_bucket2_eligible,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        cross join unnest(['Reading', 'Math']) as subject
        inner join grade_bands as gb on co.grade_level = gb.grade_level
        left join
            state_test_union as st
            on co.student_number = st.student_number
            and co.academic_year = st.academic_year_plus
            and subject = st.subject
        left join
            iready as ir
            on co.student_number = ir.student_number
            and co.academic_year = ir.academic_year
            and subject = ir.subject
        where co.rn_year = 1 and co.grade_level between 3 and 8 and co.enroll_status = 0

        union all

        select
            co.academic_year,
            co.student_number,
            co.lastfirst as student_name,
            co.region,
            co.grade_level,
            co.grade_level_prev,
            co.year_in_network,
            co.school_abbreviation as school,

            gb.band,

            subject,

            coalesce(ir.assessment_type, 'Untested') as benchmark_assessment_type,
            ir.level as performance_level,
            ir.scale_score,
            ir.is_proficient_int,
            ir.is_approaching_int,
            ir.is_below_int,
            if(ir.scale_score is not null, 1, 0) as is_tested_int,
            null as is_bucket2_eligible,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        cross join unnest(['Reading', 'Math']) as subject
        inner join grade_bands as gb on co.grade_level = gb.grade_level
        left join
            iready as ir
            on co.student_number = ir.student_number
            and co.academic_year = ir.academic_year
            and subject = ir.subject
        where co.rn_year = 1 and co.grade_level between 0 and 2 and co.enroll_status = 0
    ),

    parameter_set as (
        select
            r.academic_year,
            r.region,
            r.subject,
            r.band,

            g.grade_band_goal,

            round(
                ((sum(r.is_tested_int) * g.grade_band_goal) - sum(r.is_proficient_int))
                / sum(r.is_approaching_int),
                2
            ) as bubble_parameter,
        from roster as r
        left join
            goals as g
            on r.region = g.region
            and r.subject = g.subject
            and r.academic_year = g.academic_year
            and r.band = g.band
        group by all
    ),

    school_grade_goals as (
        select
            r.academic_year,
            r.region,
            r.school,
            r.grade_level,
            r.subject,
            p.bubble_parameter,
            p.grade_band_goal,
            sum(r.is_proficient_int) as n_proficient,
            round(avg(r.is_proficient_int), 3) as pct_proficient,
            sum(r.is_approaching_int) as n_approaching,
            round(avg(r.is_approaching_int), 3) as pct_approaching,
            sum(r.is_below_int) as n_below,
            round(avg(r.is_below_int), 3) as pct_below,
            sum(r.is_tested_int) as n_tested,
            round(avg(r.is_tested_int), 3) as pct_tested,
            ceiling(sum(r.is_approaching_int) * p.bubble_parameter) as n_bubble_to_move,
            (
                round(
                    (
                        sum(r.is_proficient_int)
                        + ceiling(sum(r.is_approaching_int) * p.bubble_parameter)
                    )
                    / sum(r.is_tested_int),
                    3
                )
            )
            - round(avg(r.is_proficient_int), 2) as pct_to_grow,
            round(
                (
                    sum(r.is_proficient_int)
                    + ceiling(sum(r.is_approaching_int) * p.bubble_parameter)
                )
                / sum(r.is_tested_int),
                3
            ) as percent_with_growth_met,
        from roster as r
        inner join
            parameter_set as p
            on r.academic_year = p.academic_year
            and r.region = p.region
            and r.subject = p.subject
            and r.band = p.band
        group by all
    )

select
    r.*,

    g.grade_band_goal,
    g.n_proficient,
    g.pct_proficient,
    g.n_approaching,
    g.pct_approaching,
    g.n_below,
    g.pct_below,
    g.n_tested,
    g.pct_tested,
    g.n_bubble_to_move,
    g.pct_to_grow,
    g.percent_with_growth_met,

    if(
        r.is_bucket2_eligible,
        rank() over (
            partition by r.school, r.grade_level, r.subject
            order by if(r.is_bucket2_eligible, r.scale_score, null) desc
        ),
        null
    ) as scale_score_rank,
    case
        when r.is_proficient_int = 1
        then 'Bucket 1'
        when
            g.n_bubble_to_move >= if(
                r.is_bucket2_eligible,
                rank() over (
                    partition by r.school, r.grade_level, r.subject
                    order by if(r.is_bucket2_eligible, r.scale_score, null) desc
                ),
                null
            )
        then 'Bucket 2'
    end as student_tier,
from roster as r
left join
    school_grade_goals as g
    on r.academic_year = g.academic_year
    and r.school = g.school
    and r.subject = g.subject
    and r.grade_level = g.grade_level
