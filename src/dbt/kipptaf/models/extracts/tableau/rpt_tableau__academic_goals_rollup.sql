with
    subject_croswalk as (
        select
            `subject`,

            if(
                `subject` = 'Reading', 'Text Study', 'Mathematics'
            ) as illuminate_subject_area,
        from unnest(['Reading', 'Math']) as `subject`
    ),

    grade_bands as (
        select 'K' as band, 0 as grade_level,
        union all
        select '1-2' as band, grade_level,
        from unnest([1, 2]) as grade_level
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
                g.illuminate_subject_area
                when 'Text Study'
                then 'Reading'
                when 'Mathematics'
                then 'Math'
                else g.illuminate_subject_area
            end as `subject`,

            max(g.grade_band_goal) as grade_band_goal,
        from {{ ref("int_assessments__academic_goals") }} as g
        inner join grade_bands as gb on g.grade_level = gb.grade_level
        group by all
    ),

    state_test_union as (
        select
            _dbt_source_relation,
            localstudentidentifier as student_number,
            academic_year,
            testscalescore as scale_score,
            testperformancelevel as `level`,

            'NJSLA' as assessment_type,

            academic_year + 1 as academic_year_plus,

            if(testperformancelevel >= 4, 1, 0) as is_proficient_int,
            if(testperformancelevel = 3, 1, 0) as is_approaching_int,
            if(testperformancelevel < 3, 1, 0) as is_below_int,

            case
                when `subject` like 'English%'
                then 'Reading'
                when
                    `subject` like 'Algebra%'
                    or `subject` in ('Mathematics', 'Geometry')
                then 'Math'
            end as `subject`,
        from {{ ref("stg_pearson__njsla") }}

        union all

        select
            s._dbt_source_relation,
            s.student_number,

            f.academic_year,
            f.scale_score,
            f.achievement_level_int as `level`,

            'FAST' as assessment_type,

            f.academic_year + 1 as academic_year_plus,

            if(f.achievement_level_int >= 3, 1, 0) as is_proficient_int,
            if(f.achievement_level_int = 2, 1, 0) as is_approaching_int,
            if(f.achievement_level_int < 2, 1, 0) as is_below_int,

            if(
                f.assessment_subject = 'English Language Arts', 'Reading', 'Math'
            ) as `subject`,
        from {{ ref("stg_fldoe__fast") }} as f
        left join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on f.student_id = suf.fleid
            and {{ union_dataset_join_clause(left_alias="f", right_alias="suf") }}
        left join
            {{ ref("stg_powerschool__students") }} as s
            on suf.studentsdcid = s.dcid
            and {{ union_dataset_join_clause(left_alias="suf", right_alias="s") }}
        where f.administration_window = 'PM3' and f.scale_score is not null
    ),

    iready as (
        select
            _dbt_source_relation,
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
        from {{ ref("base_iready__diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and projected_sublevel_number_typical is not null
            and student_grade_int between 3 and 8

        union all

        select
            _dbt_source_relation,
            student_id as student_number,
            academic_year_int as academic_year,
            `subject`,
            level_number_with_typical as `level`,

            'i-Ready BOY' as assessment_type,

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

            s.subject,

            cc.sections_section_number as course_section,
            cc.teacher_lastfirst as course_teacher_name,

            hr.sections_section_number as homeroom_section,
            hr.teacher_lastfirst as homeroom_teacher_name,

            st.scale_score as scale_score_state,
            st.is_proficient_int as is_proficient_int_state,

            ir.scale_score as scale_score_iready,

            if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

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
                    and st.is_approaching_int = 1
                then true
                when
                    coalesce(st.assessment_type, ir.assessment_type) = 'i-Ready BOY'
                    and co.grade_level <= 3
                    and ir.is_approaching_int = 1
                then true
                else false
            end as is_bucket2_eligible,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        cross join subject_croswalk as s
        inner join grade_bands as gb on co.grade_level = gb.grade_level
        inner join
            {{ ref("int_reporting__student_filters") }} as sf
            on co.academic_year = sf.academic_year
            and co.student_number = sf.student_number
            and {{ union_dataset_join_clause(left_alias="co", right_alias="sf") }}
            and s.subject = sf.iready_subject
            and not sf.is_exempt_state_testing
        left join
            {{ ref("base_powerschool__course_enrollments") }} as cc
            on co.studentid = cc.cc_studentid
            and co.yearid = cc.cc_yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="cc") }}
            and s.illuminate_subject_area = cc.illuminate_subject_area
            and not cc.is_dropped_section
            and cc.rn_student_year_illuminate_subject_desc = 1
        left join
            {{ ref("base_powerschool__course_enrollments") }} as hr
            on co.studentid = hr.cc_studentid
            and co.yearid = hr.cc_yearid
            and co.schoolid = hr.cc_schoolid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
            and hr.cc_course_number = 'HR'
            and not hr.is_dropped_section
            and hr.rn_course_number_year = 1
        left join
            state_test_union as st
            on co.student_number = st.student_number
            and co.academic_year = st.academic_year_plus
            and {{ union_dataset_join_clause(left_alias="co", right_alias="st") }}
            and s.subject = st.subject
        left join
            iready as ir
            on co.student_number = ir.student_number
            and co.academic_year = ir.academic_year
            and {{ union_dataset_join_clause(left_alias="co", right_alias="ir") }}
            and s.subject = ir.subject
        where co.rn_year = 1 and co.enroll_status = 0 and co.grade_level between 3 and 8

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

            s.subject,

            cc.sections_section_number as course_section,
            cc.teacher_lastfirst as course_teacher_name,

            hr.sections_section_number as homeroom_section,
            hr.teacher_lastfirst as homeroom_teacher_name,

            null as scale_score_state,
            null as is_proficient_int_state,
            null as scale_score_iready,

            if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

            coalesce(ir.assessment_type, 'Untested') as benchmark_assessment_type,

            ir.level as performance_level,
            ir.scale_score,
            ir.is_proficient_int,
            ir.is_approaching_int,
            ir.is_below_int,

            if(ir.scale_score is not null, 1, 0) as is_tested_int,
            if(ir.is_approaching_int = 1, true, false) as is_bucket2_eligible,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        cross join subject_croswalk as s
        inner join grade_bands as gb on co.grade_level = gb.grade_level
        inner join
            {{ ref("int_reporting__student_filters") }} as sf
            on co.academic_year = sf.academic_year
            and co.student_number = sf.student_number
            and {{ union_dataset_join_clause(left_alias="co", right_alias="sf") }}
            and s.subject = sf.iready_subject
            and not sf.is_exempt_state_testing
        left join
            {{ ref("base_powerschool__course_enrollments") }} as cc
            on co.studentid = cc.cc_studentid
            and co.yearid = cc.cc_yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="cc") }}
            and s.illuminate_subject_area = cc.illuminate_subject_area
            and not cc.is_dropped_section
            and cc.rn_student_year_illuminate_subject_desc = 1
        left join
            {{ ref("base_powerschool__course_enrollments") }} as hr
            on co.studentid = hr.cc_studentid
            and co.yearid = hr.cc_yearid
            and co.schoolid = hr.cc_schoolid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
            and hr.cc_course_number = 'HR'
            and not hr.is_dropped_section
            and hr.rn_course_number_year = 1
        left join
            iready as ir
            on co.student_number = ir.student_number
            and co.academic_year = ir.academic_year
            and {{ union_dataset_join_clause(left_alias="co", right_alias="ir") }}
            and s.subject = ir.subject
        where co.rn_year = 1 and co.enroll_status = 0 and co.grade_level between 0 and 2
    ),

    roster_ranked as (
        select
            *,

            rank() over (
                partition by academic_year, school, grade_level, subject
                order by if(is_bucket2_eligible, scale_score_state, null) desc
            ) as rank_scale_score_state,

            rank() over (
                partition by academic_year, school, grade_level, subject
                order by if(is_bucket2_eligible, scale_score, null) desc
            ) as rank_scale_score,
        from roster
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
            sum(r.is_approaching_int) as n_approaching,
            sum(r.is_below_int) as n_below,
            sum(r.is_tested_int) as n_tested,

            round(avg(r.is_proficient_int), 2) as pct_proficient,
            round(avg(r.is_proficient_int_state), 2) as pct_proficient_state,
            round(avg(r.is_approaching_int), 2) as pct_approaching,
            round(avg(r.is_below_int), 2) as pct_below,
            round(avg(r.is_tested_int), 2) as pct_tested,
        from roster as r
        inner join
            parameter_set as p
            on r.academic_year = p.academic_year
            and r.region = p.region
            and r.subject = p.subject
            and r.band = p.band
        group by all
    ),

    foo as (
        select *, ceiling(n_approaching * bubble_parameter) as n_bubble_to_move,
        from school_grade_goals
    ),

    bar as (
        select
            *,

            round(
                (n_proficient + n_bubble_to_move) / n_tested, 2
            ) as percent_with_growth_met,
        from foo
    )

select
    r.*,

    g.bubble_parameter,
    g.grade_band_goal,
    g.n_proficient,
    g.pct_proficient,
    g.pct_proficient_state,
    g.n_approaching,
    g.pct_approaching,
    g.n_below,
    g.pct_below,
    g.n_tested,
    g.pct_tested,
    g.n_bubble_to_move,
    g.percent_with_growth_met,

    g.percent_with_growth_met - g.pct_proficient as pct_to_grow,

    case
        when r.is_bucket2_eligible and r.grade_level >= 4
        then r.rank_scale_score_state
        when r.is_bucket2_eligible and r.grade_level < 4
        then r.rank_scale_score
    end as scale_score_rank,

    case
        when r.is_proficient_int = 1
        then 'Bucket 1'
        when
            r.grade_level >= 4
            and r.is_bucket2_eligible
            and g.n_bubble_to_move >= r.rank_scale_score_state
        then 'Bucket 2'
        when
            r.grade_level < 4
            and r.is_bucket2_eligible
            and g.n_bubble_to_move >= r.rank_scale_score
        then 'Bucket 2'
    end as student_tier_calculated,
from roster_ranked as r
left join
    bar as g
    on r.academic_year = g.academic_year
    and r.school = g.school
    and r.grade_level = g.grade_level
    and r.subject = g.subject
