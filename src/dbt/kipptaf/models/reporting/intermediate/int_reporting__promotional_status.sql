with
    attendance as (
        select
            mem._dbt_source_relation,
            mem.studentid,
            mem.yearid,

            rt.name as term_name,

            round(avg(mem.attendancevalue), 2) as ada_term_running,

            coalesce(sum(abs(mem.attendancevalue - 1)), 0) as n_absences_y1_running,

            coalesce(
                sum(
                    if(
                        ac.att_code not in ('ISS', 'OSS', 'OS', 'OSSP', 'SHI'),
                        abs(mem.attendancevalue - 1),
                        null
                    )
                ),
                0
            )
            + floor(sum(is_tardy) / 3) as n_absences_y1_running_non_susp,

            case
                regexp_extract(mem._dbt_source_relation, r'(kipp\w+)_')
                when 'kippnewark'
                then 27
                when 'kippcamden'
                then 36
            end as hs_at_risk_absences,

            case
                when
                    regexp_extract(mem._dbt_source_relation, r'(kipp\w+)_')
                    = 'kippnewark'
                then 6 * safe_cast(right(rt.name, 1) as int)
                when
                    regexp_extract(mem._dbt_source_relation, r'(kipp\w+)_')
                    = 'kippcamden'
                then 9 * safe_cast(right(rt.name, 1) as int)
            end as hs_off_track_absences,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on mem.schoolid = rt.school_id
            and mem.yearid = rt.powerschool_year_id
            /* join to all terms after calendardate */
            and mem.calendardate <= rt.end_date
            and rt.type = 'RT'
        left join
            {{ ref("stg_powerschool__attendance") }} as att
            on mem.studentid = att.studentid
            and mem.calendardate = att.att_date
            and mem.schoolid = att.schoolid
            and att.att_mode_code = 'ATT_ModeDaily'
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="att") }}
        left join
            {{ ref("stg_powerschool__attendance_code") }} as ac
            on att.attendance_codeid = ac.id
            and att.yearid = ac.yearid
            and att.schoolid = ac.schoolid
            and {{ union_dataset_join_clause(left_alias="att", right_alias="ac") }}
        where
            mem.membershipvalue = 1
            and mem.calendardate <= current_date('{{ var("local_timezone") }}')
        group by mem._dbt_source_relation, mem.yearid, mem.studentid, rt.name
    ),

    credits as (
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
        from {{ ref("base_iready__diagnostic_results") }}
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
                cast(right(state_benchmark_category_name, 1) as int64),
                5 - district_benchmark_category_level
            ) as star_achievement_level,
        from {{ ref("int_renlearn__star_rollup") }}
        where rn_subj_year = 1
    ),

    star as (
        select
            student_display_id,
            academic_year,
            `ELA` as star_ela_level,
            `Math` as star_math_level,
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
            ) pivot (
                max(achievement_level_int) for assessment_subject
                in ('English Language Arts' as fast_ela, 'Mathematics' as fast_math)
            )
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
        from {{ ref("int_powerschool__log") }}
        where logtype_name = 'Exempt from retention'
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
        from {{ ref("int_powerschool__log") }}
        where logtype_name = 'Retain without criteria'
    ),

    promo as (
        select
            co.student_number,
            co.academic_year,
            co.grade_level,
            co.is_self_contained,
            co.special_education_code,
            co.region,

            rt.name as term_name,
            rt.is_current,

            att.ada_term_running,
            att.n_absences_y1_running,
            att.n_absences_y1_running_non_susp,

            ir.iready_reading_recent,
            ir.iready_math_recent,

            c.n_failing,
            c.n_failing_core,
            c.projected_credits_y1_term,
            c.projected_credits_cum,

            m.measure_standard_level as dibels_composite_level_recent_str,
            m.measure_standard_level_int as dibels_composite_level_recent,

            s.star_math_level as star_math_level_recent,
            s.star_ela_level as star_reading_level_recent,

            f.fast_ela as fast_ela_level_recent,
            f.fast_math as fast_math_level_recent,

            case
                when
                    co.grade_level < 3
                    and co.is_self_contained
                    and co.special_education_code in ('CMI', 'CMO', 'CSE')
                then 'Exempt - Special Education'
                when
                    co.grade_level between 3 and 8
                    and (
                        co.ela_state_assessment_name = '3'
                        or co.math_state_assessment_name in ('3', '4')
                    )
                then 'Exempt - Special Education'
                when lg.entry_date is not null
                then 'Exempt - Manual Override'
            end as exemption,

            if(fr.entry_date is not null, 'Manual Retention', null) as manual_retention,

            case
                /* NJ Gr K-8 */
                when
                    co.region in ('Camden', 'Newark')
                    and co.grade_level <= 8
                    and att.ada_term_running is null
                then 'Off-Track'
                /* NJ Gr K */
                when
                    co.region = 'Newark'
                    and co.grade_level = 0
                    and att.ada_term_running < 0.85
                then 'Off-Track'
                when
                    co.region = 'Camden'
                    and co.grade_level = 0
                    and att.ada_term_running < 0.82
                then 'Off-Track'
                /* NJ Gr 1-2 */
                when
                    co.region = 'Newark'
                    and co.grade_level between 1 and 2
                    and att.ada_term_running < 0.87
                then 'Off-Track'
                when
                    co.region = 'Newark'
                    and co.grade_level between 1 and 2
                    and att.ada_term_running < 0.86
                then 'Off-Track'
                /* NJ Gr3-8 */
                when
                    co.grade_level between 3 and 8
                    and co.region = 'Camden'
                    and att.ada_term_running < 0.87
                then 'Off-Track'
                when
                    co.grade_level between 3 and 8
                    and co.region = 'Newark'
                    and att.ada_term_running < 0.9
                then 'Off-Track'
                /* Miami K */
                when
                    co.region = 'Miami'
                    and co.grade_level = 0
                    and att.ada_term_running < 0.80
                then 'Off-Track'
                /* Miami Gr1-2, 4 */
                when
                    co.region = 'Miami'
                    and co.grade_level in (1, 2, 4)
                    and att.ada_term_running < 0.85
                then 'Off-Track'
                /* Miami Gr5-8*/
                when
                    co.region = 'Miami'
                    and co.grade_level in (1, 2, 4)
                    and (att.ada_term_running < 0.85 or att.n_absences_y1_running >= 27)
                then 'Off-Track'
                /* HS */
                when
                    co.grade_level >= 9
                    and att.n_absences_y1_running_non_susp >= att.hs_at_risk_absences
                then 'Off-Track'
                when
                    co.grade_level >= 9
                    and att.n_absences_y1_running_non_susp >= att.hs_off_track_absences
                then 'Off-Track'
                else 'On-Track'
            end as attendance_status,

            case
                /* NJ Gr K-8 */
                when
                    co.region in ('Camden', 'Newark')
                    and co.grade_level <= 8
                    and att.ada_term_running is null
                then 'Off-Track'
                /* NJ Gr K */
                when
                    co.region = 'Newark'
                    and co.grade_level = 0
                    and att.ada_term_running < 0.85
                then 'Off-Track'
                when
                    co.region = 'Camden'
                    and co.grade_level = 0
                    and att.ada_term_running < 0.82
                then 'Off-Track'
                /* NJ Gr 1-2 */
                when
                    co.region = 'Newark'
                    and co.grade_level between 1 and 2
                    and att.ada_term_running < 0.87
                then 'Off-Track'
                when
                    co.region = 'Newark'
                    and co.grade_level between 1 and 2
                    and att.ada_term_running < 0.86
                then 'Off-Track'
                /* NJ Gr3-8 */
                when
                    co.grade_level between 3 and 8
                    and co.region = 'Camden'
                    and att.ada_term_running < 0.87
                then 'Off-Track'
                when
                    co.grade_level between 3 and 8
                    and co.region = 'Newark'
                    and att.ada_term_running < 0.9
                then 'Off-Track'
                /* Miami K */
                when
                    co.region = 'Miami'
                    and co.grade_level = 0
                    and att.ada_term_running < 0.80
                then 'Off-Track'
                /* Miami Gr1-2, 4 */
                when
                    co.region = 'Miami'
                    and co.grade_level in (1, 2, 4)
                    and att.ada_term_running < 0.85
                then 'Off-Track'
                /* Miami Gr5-8*/
                when
                    co.region = 'Miami'
                    and co.grade_level in (1, 2, 4)
                    and (att.ada_term_running < 0.85 or att.n_absences_y1_running >= 27)
                then 'Off-Track'
                /* HS */
                when
                    co.grade_level >= 9
                    and att.n_absences_y1_running_non_susp >= att.hs_at_risk_absences
                then 'Off-Track (Already reached threshold)'
                when
                    co.grade_level >= 9
                    and att.n_absences_y1_running_non_susp >= att.hs_off_track_absences
                then 'Off-Track (Approaching threshold)'
                else 'On-Track'
            end as attendance_status_hs_detail,

            case
                /* GrK-1 NJ */
                when
                    co.region in ('Camden', 'Newark')
                    and co.grade_level <= 1
                    and coalesce(m.measure_standard_level_int, 0) <= 1
                then 'Off-Track'
                /* Gr2 NJ */
                when
                    co.region in ('Camden', 'Newark')
                    and co.grade_level = 2
                    and coalesce(ir.iready_reading_recent, '')
                    in ('2 Grade Levels Below', '3 or More Grade Levels Below', '')
                then 'Off-Track'
                /* Gr3-8 NJ */
                when
                    co.region in ('Camden', 'Newark')
                    and co.grade_level between 3 and 8
                    and (
                        coalesce(ir.iready_reading_recent, '')
                        in ('2 Grade Levels Below', '3 or More Grade Levels Below', '')
                        and coalesce(ir.iready_math_recent, '')
                        in ('2 Grade Levels Below', '3 or More Grade Levels Below', '')
                    )
                    or c.n_failing_core >= 2
                then 'Off-Track'

                /* Miami K-3 */
                when
                    co.region = 'Miami'
                    and co.grade_level < 3
                    and (s.star_math_level = 1 or s.star_ela_level = 1)
                then 'Off-Track'
                when co.region = 'Miami' and co.grade_level = 3 and f.fast_ela = 1
                then 'Off-Track'
                /* Miami Gr4 */
                when
                    co.region = 'Miami'
                    and co.grade_level = 4
                    and f.fast_math = 1
                    and f.fast_ela = 1
                then 'Off-Track'
                /* Miami 5-8 */
                when
                    co.region = 'Miami' and co.grade_level > 4 and c.n_failing_core >= 2
                then 'Off-Track'
                /* HS */
                when co.grade_level = 9 and c.projected_credits_cum < 25
                then 'Off-Track'
                when co.grade_level = 10 and c.projected_credits_cum < 50
                then 'Off-Track'
                when co.grade_level = 11 and c.projected_credits_cum < 85
                then 'Off-Track'
                when co.grade_level = 12 and c.projected_credits_cum < 120
                then 'Off-Track'
                else 'On-Track'
            end as academic_status,
        from {{ ref("int_extracts__student_enrollments") }} as co
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
        left join
            fast as f on co.fleid = f.student_id and co.academic_year = f.academic_year
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
    )

select
    student_number,
    academic_year,
    term_name,
    is_current,
    ada_term_running,
    n_absences_y1_running,
    n_absences_y1_running_non_susp,
    iready_reading_recent,
    iready_math_recent,
    n_failing,
    n_failing_core,
    projected_credits_cum,
    projected_credits_y1_term,
    dibels_composite_level_recent_str,
    dibels_composite_level_recent,
    star_math_level_recent,
    star_reading_level_recent,
    fast_ela_level_recent,
    fast_math_level_recent,
    attendance_status,
    attendance_status_hs_detail,
    academic_status,
    exemption,
    manual_retention,

    case
        /* NJ */
        when
            region in ('Camden', 'Newark')
            and grade_level <= 8
            and academic_status = 'Off-Track'
            and attendance_status = 'Off-Track'
        then 'Off-Track'
        when
            region in ('Camden', 'Newark')
            and grade_level between 5 and 8
            and n_failing_core >= 2
        then 'Off-Track'
        when
            region in ('Camden', 'Newark')
            and grade_level >= 9
            and (academic_status = 'Off-Track' or attendance_status = 'Off-Track')
        then 'Off-Track'
        /* Miami */
        when
            region = 'Miami'
            and grade_level != 4
            and (academic_status = 'Off-Track' or attendance_status = 'Off-Track')
        then 'Off-Track'
        when
            region = 'Miami'
            and grade_level = 4
            and academic_status = 'Off-Track'
            and attendance_status = 'Off-Track'
        then 'Off-Track'
        else 'On-Track'
    end as overall_status,
from promo
