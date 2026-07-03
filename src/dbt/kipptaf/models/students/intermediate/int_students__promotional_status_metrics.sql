with
    attendance as (
        select
            mem._dbt_source_relation,
            mem.studentid,
            mem.yearid,

            rt.name as term_name,

            round(avg(mem.attendancevalue), 2) as ada_term_running,

            coalesce(sum(mem.is_absent), 0) as n_absences_y1_running,

            coalesce(sum(mem.is_absent_non_susp), 0)
            + floor(sum(mem.is_tardy) / 3) as n_absences_y1_running_non_susp,

            coalesce(
                sum(mem.is_absent_non_susp), 0
            ) as n_absences_y1_running_non_susp_no_tardy,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on mem.schoolid = rt.school_id
            and mem.yearid = rt.powerschool_year_id
            /* join to all terms after calendardate */
            and mem.calendardate <= rt.end_date
            and rt.type = 'RT'
        where
            mem.membershipvalue = 1
            and mem.calendardate <= current_date('{{ var("local_timezone") }}')
        group by mem._dbt_source_relation, mem.yearid, mem.studentid, rt.name
    ),

    credits as (
        -- TODO(#3900): final_grades_rollup PS double-write fans out ~4 Newark
        -- rows/term; expected uniqueness warn, no dedupe per repo convention
        select
            fg._dbt_source_relation,
            fg.studentid,
            fg.academic_year,
            fg.storecode,
            fg.enrolled_credit_hours,
            fg.n_failing,
            fg.n_failing_core,
            fg.projected_credits_y1_term,

            coalesce(fg.projected_credits_y1_term, 0)
            + coalesce(gc.earned_credits_cum, 0) as projected_credits_cum,
        from {{ ref("int_powerschool__final_grades_rollup") }} as fg
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on fg.studentid = gc.studentid
            and fg.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="fg", right_alias="gc") }}
    ),

    iready_dr as (
        select
            student_id,
            academic_year_int,
            `subject`,
            most_recent_overall_relative_placement,
        from {{ ref("int_iready__diagnostic_results") }}
    ),

    iready as (
        select student_id, academic_year_int, iready_reading_recent, iready_math_recent,
        from
            iready_dr pivot (
                max(most_recent_overall_relative_placement) for `subject`
                in ('Reading' as iready_reading_recent, 'Math' as iready_math_recent)
            )
    ),

    mclass as (
        select
            academic_year,
            student_number,
            measure_standard_level,
            measure_standard_level_int,
            client_date,

            row_number() over (
                partition by academic_year, student_number order by client_date desc
            ) as rn_composite,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark' and measure_name_code = 'Composite'
    ),

    star_results as (
        select
            student_display_id,
            academic_year,
            star_discipline,

            if(
                grade_level > 0,
                cast(right(state_benchmark_category_name, 1) as int),
                5 - district_benchmark_category_level
            ) as star_achievement_level,
        from {{ ref("stg_renlearn__star") }}
        where rn_subject_year = 1
    ),

    star as (
        select
            student_display_id,
            academic_year,
            ela as star_ela_level,
            math as star_math_level,
        from
            star_results
            pivot (max(star_achievement_level) for star_discipline in ('ELA', 'Math'))
    ),

    fast_results as (
        select
            student_id,
            academic_year,
            assessment_subject,
            achievement_level_int,

            row_number() over (
                partition by student_id, academic_year, assessment_subject
                order by administration_window desc
            ) as rn_subject_year,
        from {{ ref("stg_fldoe__fast") }}
    ),

    fast as (
        select student_id, academic_year, fast_ela, fast_math,
        from
            (
                select
                    f.student_id,
                    f.academic_year,
                    f.assessment_subject,
                    f.achievement_level_int,
                from fast_results as f
                where f.rn_subject_year = 1
            ) as fast_filtered pivot (
                max(achievement_level_int) for assessment_subject
                in ('English Language Arts' as fast_ela, 'Mathematics' as fast_math)
            )
    ),

    ps_log as (
        select
            lg._dbt_source_relation,
            lg.studentid,
            lg.academic_year,
            lg.entry_date,
            lg.entry,

            g.name,
        from {{ ref("stg_powerschool__log") }} as lg
        inner join
            {{ ref("stg_powerschool__gen") }} as g
            on lg.logtypeid = g.id
            and g.cat = 'logtype'
            and g.name in ('Exempt from retention', 'Retain without criteria')
    ),

    exempt_override as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            entry_date,
            `entry`,

            row_number() over (
                partition by _dbt_source_relation, studentid, academic_year
                order by entry_date desc
            ) as rn_log,
        from ps_log
        where name = 'Exempt from retention'
    ),

    force_retention as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            entry_date,
            `entry`,

            row_number() over (
                partition by _dbt_source_relation, studentid, academic_year
                order by entry_date desc
            ) as rn_log,
        from ps_log
        where name = 'Retain without criteria'
    )

select
    co.student_number,
    co.academic_year,
    co.region,
    co.grade_level,

    rt.name as term_name,
    rt.is_current,

    att.ada_term_running,
    att.n_absences_y1_running,
    att.n_absences_y1_running_non_susp,
    att.n_absences_y1_running_non_susp_no_tardy,

    ir.iready_reading_recent,
    ir.iready_math_recent,

    c.n_failing,
    c.n_failing_core,
    c.projected_credits_y1_term,
    c.projected_credits_cum,

    m.measure_standard_level as dibels_composite_level_recent_str,
    m.measure_standard_level_int as dibels_composite_level,

    s.star_ela_level,
    s.star_math_level,

    f.fast_ela as fast_ela_level,
    f.fast_math as fast_math_level,

    if(fr.entry_date is not null, 'Manual Retention', null) as manual_retention,

    case
        ir.iready_reading_recent
        when '3 or More Grade Levels Below'
        then 3
        when '2 Grade Levels Below'
        then 2
        when '1 Grade Level Below'
        then 1
        when 'Early On Grade Level'
        then 0
        when 'Mid or Above Grade Level'
        then 0
    end as iready_reading_levels_below,

    case
        ir.iready_math_recent
        when '3 or More Grade Levels Below'
        then 3
        when '2 Grade Levels Below'
        then 2
        when '1 Grade Level Below'
        then 1
        when 'Early On Grade Level'
        then 0
        when 'Mid or Above Grade Level'
        then 0
    end as iready_math_levels_below,

    case
        when
            co.grade_level < 3
            and co.is_self_contained
            and co.special_education_code in ('CMI', 'CMO', 'CSE')
        then 'Exempt - Special Education'
        when
            co.grade_level between 3 and 8
            and (
                nj.state_assessment_name = '3'
                or nj.math_state_assessment_name in ('3', '4')
            )
        then 'Exempt - Special Education'
        when lg.entry_date is not null
        then 'Exempt - Manual Override'
    end as exemption,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on co.academic_year = rt.academic_year
    and co.schoolid = rt.school_id
    and rt.type = 'RT'
left join
    attendance as att
    on co.studentid = att.studentid
    and co.yearid = att.yearid
    and rt.name = att.term_name
    and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
left join
    credits as c
    on co.studentid = c.studentid
    and co.academic_year = c.academic_year
    and rt.name = c.storecode
    and {{ union_dataset_join_clause(left_alias="co", right_alias="c") }}
left join
    iready as ir
    on co.student_number = ir.student_id
    and co.academic_year = ir.academic_year_int
left join
    mclass as m
    on co.academic_year = m.academic_year
    and co.student_number = m.student_number
    and m.rn_composite = 1
left join
    star as s
    on co.student_number = s.student_display_id
    and co.academic_year = s.academic_year
left join fast as f on co.fleid = f.student_id and co.academic_year = f.academic_year
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
    on co.students_dcid = nj.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
left join
    exempt_override as lg
    on co.studentid = lg.studentid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="lg") }}
    and co.academic_year = lg.academic_year
    and lg.rn_log = 1
left join
    force_retention as fr
    on co.studentid = fr.studentid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="fr") }}
    and co.academic_year = fr.academic_year
    and fr.rn_log = 1
where co.rn_year = 1
