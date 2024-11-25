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
            ) as n_absences_y1_running_non_susp,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        inner join
            {{ ref("stg_reporting__terms") }} as rt
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

    credits as (
        select
            fg._dbt_source_relation,
            fg.studentid,
            fg.academic_year,
            fg.storecode,
            fg.n_failing_core,

            coalesce(fg.projected_credits_y1_term, 0)
            + coalesce(gc.earned_credits_cum, 0) as projected_credits_cum,
        from fg_credits as fg
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on fg.studentid = gc.studentid
            and fg.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="fg", right_alias="gc") }}
    ),

    star as (
        select
            student_display_id,
            academic_year,
            star_discipline,
            state_benchmark_category_level,
            state_benchmark_category_name,
        from {{ ref("int_renlearn__star_rollup") }}
        where rn_subj_year = 1
    ),

    fast as (
        select
            s.student_number,

            f.academic_year,
            f.discipline,
            f.achievement_level_int,
            f.achievement_level,
            f.administration_window,

            row_number() over (
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

            ada_running,
            projected_credits_cum,
            days_absent_running,
            n_failing_core,
            iready_reading_orp_recent,
            iready_math_orp_recent,
            dibels_composite_recent,
            star_ela_achievement_level,
            star_math_achievement_level,
            fast_ela_achievement_level,
            fast_math_achievement_level,

            case
                /* NJ grades k-1 */
                when
                    region in ('Camden', 'Newark')
                    and grade_level between 0 and 1
                    and not is_on_track_dibels
                then 'Off-Track'
                /* NJ grade 2 */
                when
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
                then 'Off-Track'
                /* NJ HS */
                when
                    region in ('Camden', 'Newark')
                    and grade_level >= 9
                    and not is_on_track_projected_credits
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
        then 'Off-Track'
        else 'On-Track'
    end as overall_status,
from status_detail as s
left join
    hs_absence_threshold as hs
    on s.academic_year = hs.academic_year
    and s.region = hs.region
    and s.grade_level = hs.grade_level
where s.region = 'Miami'
