with
    hs_absence_threshold as (
        select region, academic_year, grade_level, cutoff
        from {{ ref("stg_reporting__promo_status_cutoffs") }}
        where code = 'Q4' and subject = 'Days Absent'
    ),

    attendance as (
        select
            mem.studentid,
            mem._dbt_source_relation,

            rt.name as term_name,

            mem.yearid + 1990 as academic_year,

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
<<<<<<< HEAD
            ) as n_absences_y1_running_non_susp,
=======
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
>>>>>>> main
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

<<<<<<< HEAD
    mclass as (
        select
            a.mclass_academic_year as academic_year,
            a.mclass_student_number as student_number,
            a.mclass_measure_standard_level,
            a.mclass_measure_standard_level_int,
            a.mclass_client_date,

            term_name,

            row_number() over (
                partition by a.mclass_academic_year, a.mclass_student_number, term_name
                order by a.mclass_client_date desc
            ) as rn_composite,
        from {{ ref("int_amplify__all_assessments") }} as a
        cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term_name
        where assessment_type = 'Benchmark' and mclass_measure_name_code = 'Composite'
    ),

    fg_credits as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            schoolid,
            storecode,

            sum(potential_credit_hours) as enrolled_credit_hours,

            sum(if(y1_letter_grade_adjusted in ('F', 'F*'), 1, 0)) as n_failing,
            sum(
                if(
                    y1_letter_grade_adjusted in ('F', 'F*')
                    and credittype in ('ENG', 'MATH', 'SCI', 'SOC'),
                    1,
                    0
                )
            ) as n_failing_core,
            sum(
                if(
                    {# TODO: exclude credits if current year Y1 is stored #}
                    y1_letter_grade_adjusted not in ('F', 'F*'),
                    potential_credit_hours,
                    null
                )
            ) as projected_credits_y1_term,
        from {{ ref("base_powerschool__final_grades") }}
        group by _dbt_source_relation, studentid, academic_year, schoolid, storecode
    ),

=======
>>>>>>> main
    credits as (
        select
            fg._dbt_source_relation,
            fg.studentid,
            fg.academic_year,
            fg.storecode,
            fg.n_failing_core,
            fg.n_failing,

            coalesce(fg.projected_credits_y1_term, 0)
            + coalesce(gc.earned_credits_cum, 0) as projected_credits_cum,
        from {{ ref("int_powerschool__final_grades_rollup") }} as fg
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on fg.studentid = gc.studentid
            and fg.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="fg", right_alias="gc") }}
    ),

<<<<<<< HEAD
=======
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

>>>>>>> main
    star as (
        select
            student_display_id,
            academic_year,
<<<<<<< HEAD
            star_discipline,
            state_benchmark_category_level,
            state_benchmark_category_name,
        from {{ ref("int_renlearn__star_rollup") }}
        where rn_subj_year = 1
    ),

    fast as (
        select
            s.student_number,
=======
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
>>>>>>> main

            f.academic_year,
            f.discipline,
            f.achievement_level_int,
            f.achievement_level,
            f.administration_window,

            row_number() over (
<<<<<<< HEAD
                partition by f.student_id, f.academic_year, f.discipline
                order by f.administration_window desc
            ) as rn_fast_year,
        from {{ ref("stg_fldoe__fast") }} as f
        inner join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on f.student_id = suf.fleid
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on suf.studentsdcid = s.dcid
            and {{ union_dataset_join_clause(left_alias="suf", right_alias="s") }}
=======
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
>>>>>>> main
    ),

    metric_union_sid as (
        select
            'Attendance' as discipline,
            'ADA' as subject,

            studentid,
            _dbt_source_relation,
            academic_year,
            term_name,
            ada_term_running as metric,
            cast(ada_term_running as string) as metric_display,
        from attendance

        union all

        select
            'Attendance' as discipline,
            'Days Absent' as subject,

            studentid,
            _dbt_source_relation,
            academic_year,
            term_name,
            n_absences_y1_running_non_susp as metric,
            cast(n_absences_y1_running as string) as metric_display,
        from attendance

        union all

        select
            'Academics' as discipline,
            'Core Fs' as subject,

            studentid,
            _dbt_source_relation,
            academic_year,
            storecode as term_name,
            n_failing_core as metric,
            cast(n_failing_core as string) as metric_display,
        from credits

        union all

        select
            'Academics' as discipline,
            'N Failing' as subject,

            studentid,
            _dbt_source_relation,
            academic_year,
            storecode as term_name,
            n_failing as metric,
            cast(n_failing as string) as metric_display,
        from credits

        union all

        select
            'Academics' as discipline,
            'Projected Credits' as subject,

            studentid,
            _dbt_source_relation,
            academic_year,
            storecode as term_name,
            projected_credits_cum as metric,
            cast(projected_credits_cum as string) as metric_display,
        from credits
    ),

    metric_union_sn as (
        select
            'Academics' as discipline,
            'DIBELS Benchmark' as subject,

            student_number,
            academic_year,
            term_name,
            mclass_measure_standard_level_int as metric,
            mclass_measure_standard_level as metric_display,
        from mclass
        where rn_composite = 1

        union all

        select
            'Academics' as discipline,
            concat('i-Ready ', i.subject) as subject,

            i.student_id as student_number,
            i.academic_year_int as academic_year,
            term_name,
            i.most_recent_overall_relative_placement_int as metric,
            i.most_recent_overall_relative_placement as metric_display,
        from {{ ref("base_iready__diagnostic_results") }} as i
        cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term_name

        union all

        select
            'Academics' as discipline,
            concat('Star ', s.star_discipline) as subject,

            student_display_id as student_number,
            academic_year,
            term_name,
            state_benchmark_category_level as metric,
            state_benchmark_category_name as metric_display,
        from star as s
        cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term_name

        union all

        select
            'Academics' as discipline,
            concat('FAST ', discipline) as subject,

            student_number,
            academic_year,
            term_name,
            achievement_level_int as metric,
            achievement_level as metric_display,
        from fast as s
        cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term_name
    ),

    identifiers as (
        select
            co.student_number,
            co.academic_year,
            co.region,
            co.grade_level,
            co.is_self_contained,
            co.special_education_code,
            co.region,

<<<<<<< HEAD
            ps.subject,
            ps.code as term_name,

            mu.metric_display,

            case
                when ps.sf_standardized_test = 'golf' and mu.metric < ps.cutoff
                then true
                when ps.sf_standardized_test = 'baseball' and mu.metric >= ps.cutoff
                then true
                else false
            end as is_on_track,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_reporting__promo_status_cutoffs") }} as ps
            on co.academic_year = ps.academic_year
            and co.region = ps.region
            and co.grade_level = ps.grade_level
            and ps.domain = 'Promotion'
            and ps.type = 'studentid'
        left join
            metric_union_sid as mu
            on co.studentid = mu.studentid
            and co.academic_year = mu.academic_year
            and ps.code = mu.term_name
            and ps.discipline = mu.discipline
            and ps.subject = mu.subject
            and {{ union_dataset_join_clause(left_alias="co", right_alias="mu") }}
        where
            co.academic_year >= {{ var("current_academic_year") - 1 }}
            and co.rn_year = 1
            and co.enroll_status = 0

        union all

        select
            co.student_number,
            co.academic_year,
            co.region,
            co.grade_level,
            co.is_self_contained,
            co.special_education_code,

            ps.subject,
            ps.code as term_name,

            mu.metric_display,

            case
                when ps.sf_standardized_test = 'golf' and mu.metric < ps.cutoff
                then true
                when ps.sf_standardized_test = 'baseball' and mu.metric >= ps.cutoff
                then true
                else false
            end as is_on_track,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_reporting__promo_status_cutoffs") }} as ps
            on co.academic_year = ps.academic_year
            and co.region = ps.region
            and co.grade_level = ps.grade_level
            and ps.domain = 'Promotion'
            and ps.type = 'student_number'
        left join
            metric_union_sn as mu
            on co.student_number = mu.student_number
            and co.academic_year = mu.academic_year
            and ps.code = mu.term_name
            and ps.discipline = mu.discipline
            and ps.subject = mu.subject
        where
            co.academic_year >= {{ var("current_academic_year") - 1 }}
            and co.rn_year = 1
            and co.enroll_status = 0
    ),

    identifiers_pivot as (
        select
            student_number,
            academic_year,
            region,
            grade_level,
            is_self_contained,
            special_education_code,
            term_name,
=======
            rt.name as term_name,
            rt.is_current,
>>>>>>> main

            `is_on_track_ADA` as is_on_track_ada,
            `is_on_track_Days Absent` as is_on_track_days_absent,
            `is_on_track_i-Ready Reading` as is_on_track_iready_reading,
            `is_on_track_i-Ready Math` as is_on_track_iready_math,
            `is_on_track_DIBELS Benchmark` as is_on_track_dibels,
            `is_on_track_Core Fs` as is_on_track_core_f,
            `is_on_track_Projected Credits` as is_on_track_projected_credits,
            `is_on_track_Star ELA` as is_on_track_star_ela,
            `is_on_track_Star Math` as is_on_track_star_math,
            `is_on_track_FAST ELA` as is_on_track_fast_ela,
            `is_on_track_FAST Math` as is_on_track_fast_math,

            cast(`metric_display_ADA` as float64) as ada_running,
            cast(
                `metric_display_Projected Credits` as float64
            ) as projected_credits_cum,
            cast(`metric_display_Days Absent` as int) as days_absent_running,
            cast(`metric_display_Core Fs` as int) as n_failing_core,
            cast(`metric_display_N Failing` as int) as n_failing,
            cast(
                `metric_display_i-Ready Reading` as string
            ) as iready_reading_orp_recent,
            cast(`metric_display_i-Ready Math` as string) as iready_math_orp_recent,
            cast(
                `metric_display_DIBELS Benchmark` as string
            ) as dibels_composite_recent,
            cast(`metric_display_Star ELA` as string) as star_ela_achievement_level,
            cast(`metric_display_Star Math` as string) as star_math_achievement_level,
            cast(`metric_display_FAST ELA` as string) as fast_ela_achievement_level,
            cast(`metric_display_FAST Math` as string) as fast_math_achievement_level,
        from
            identifiers pivot (
                max(metric_display) as metric_display,
                max(is_on_track) as is_on_track for subject in (
                    'ADA',
                    'Days Absent',
                    'i-Ready Reading',
                    'i-Ready Math',
                    'DIBELS Benchmark',
                    'Core Fs',
                    'N Failing',
                    'Projected Credits',
                    'Star ELA',
                    'Star Math',
                    'FAST ELA',
                    'FAST Math'
                )
            )
    ),

    status_detail as (
        select
            student_number,
            academic_year,
            region,
            grade_level,
            is_self_contained,
            special_education_code,
            term_name,

<<<<<<< HEAD
            ada_running,
            projected_credits_cum,
            days_absent_running,
            n_failing,
            n_failing_core,
            iready_reading_orp_recent,
            iready_math_orp_recent,
            dibels_composite_recent,
            star_ela_achievement_level,
            star_math_achievement_level,
            fast_ela_achievement_level,
            fast_math_achievement_level,
=======
            m.measure_standard_level as dibels_composite_level_recent_str,
            m.measure_standard_level_int as dibels_composite_level_recent,

            s.star_math_level as star_math_level_recent,
            s.star_ela_level as star_reading_level_recent,

            f.fast_ela as fast_ela_level_recent,
            f.fast_math as fast_math_level_recent,
>>>>>>> main

            case
                /* NJ grades k-1 */
                when
                    region in ('Camden', 'Newark')
                    and grade_level between 0 and 1
                    and not is_on_track_dibels
                then 'Off-Track'
                /* NJ grade 2 */
                when
<<<<<<< HEAD
                    region in ('Camden', 'Newark')
                    and grade_level = 2
                    and not is_on_track_iready_math
                then 'Off-Track'
                /* NJ grades 3-8 */
                when
                    region in ('Camden', 'Newark')
                    and grade_level between 3 and 8
                    and (not is_on_track_iready_math and not is_on_track_iready_reading)
                    or not is_on_track_core_f
=======
                    co.grade_level between 3 and 8
                    and (
                        nj.state_assessment_name = '3'
                        or nj.math_state_assessment_name in ('3', '4')
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
                    co.region = 'Camden'
                    and co.grade_level between 1 and 2
                    and att.ada_term_running < 0.86
                then 'Off-Track'
                /* NJ Gr3-8 */
                when
                    co.grade_level between 3 and 8
                    and co.region = 'Camden'
                    and att.ada_term_running < 0.87
>>>>>>> main
                then 'Off-Track'
                /* NJ HS */
                when
<<<<<<< HEAD
                    region in ('Camden', 'Newark')
                    and grade_level >= 9
                    and not is_on_track_projected_credits
=======
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
>>>>>>> main
                then 'Off-Track'
                /* Miami K-2 */
                when
                    region = 'Miami'
                    and grade_level <= 2
                    and (not is_on_track_star_ela or not is_on_track_star_math)
                then 'Off-Track'
                /* Miami Gr3 */
                when region = 'Miami' and grade_level = 3 and not is_on_track_fast_ela
                then 'Off-Track'
                /* Miami Gr4 */
                when
                    region = 'Miami'
                    and grade_level = 4
                    and (not is_on_track_fast_ela and not_is_on_track_fast_math)
                then 'Off-Track'
<<<<<<< HEAD
                /* Miami 5-8 */
                when region = 'Miami' and grade_level >= 5 and not is_on_track_core_f
                then 'Off-Track'
                else 'On-Track'
            end as academic_status,

            case
                /* NJ grades K-8 */
                when
                    region in ('Camden', 'Newark')
                    and grade_level <= 8
                    and not is_on_track_ada
                then 'Off-Track'
                /* NJ HS */
                when
                    region in ('Camden', 'Newark')
                    and grade_level >= 9
                    and not is_on_track_days_absent
                then 'Off-Track'
                /* Miami K */
                when
                    region = 'Miami'
                    and grade_level in (0, 1, 2, 4)
                    and not is_on_track_ada
                then 'Off-Track'
                when
                    region = 'Miami'
                    and grade_level >= 5
                    and (not is_on_track_ada or not is_on_track_days_absent)
                then 'Off-Track'
                else 'On-Track'
            end as attendance_status,
        from identifiers_pivot
    )

select
    s.student_number,
    s.academic_year,
    s.region,
    s.grade_level,
    s.is_self_contained,
    s.special_education_code,
    s.term_name,

    s.ada_running,
    s.projected_credits_cum,
    s.days_absent_running,
    s.n_failing,
    s.n_failing_core,
    s.iready_reading_orp_recent,
    s.iready_math_orp_recent,
    s.dibels_composite_recent,
    s.star_ela_achievement_level,
    s.star_math_achievement_level,
    s.fast_ela_achievement_level,
    s.fast_math_achievement_level,

    s.academic_status,
    s.attendance_status,

    case
        when s.grade_level >= 9 and s.days_absent_running >= hs.cutoff
        then 'Off-Track (Already reached threshold)'
        when s.grade_level >= 9 and s.attendance_status = 'Off-Track'
        then 'Off-Track (Approaching threshold)'
        else s.attendance_status
    end as attendance_status_hs_detail,

    case
        /* NJ k-4 */
        when
            s.region in ('Camden', 'Newark')
            and s.grade_level <= 4
            and s.academic_status = 'Off-Track'
            and s.attendance_status = 'Off-Track'
        then 'Off-Track'
        /* NJ MS */
        when
            s.region in ('Camden', 'Newark')
            and s.grade_level between 5 and 8
            and s.academic_status = 'Off-Track'
            and s.attendance_status = 'Off-Track'
        then 'Off-Track'
        when
            s.region in ('Camden', 'Newark')
            and s.grade_level between 5 and 8
            and s.n_failing_core >= 2
        then 'Off-Track'
        /* NJ HS */
        when
            s.region in ('Camden', 'Newark')
            and s.grade_level >= 9
            and (s.academic_status = 'Off-Track' or s.attendance_status = 'Off-Track')
=======
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
        left join
            fast as f on co.fleid = f.student_id and co.academic_year = f.academic_year
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
>>>>>>> main
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
from status_detail as s
left join
    hs_absence_threshold as hs
    on s.academic_year = hs.academic_year
    and s.region = hs.region
    and s.grade_level = hs.grade_level
