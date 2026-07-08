with
    term as (
        select
            _dbt_source_relation,
            schoolid,
            yearid,

            term as `quarter`,

            term_start_date as quarter_start_date,
            term_end_date as quarter_end_date,

            is_current_term as is_current_quarter,
            semester,

        from {{ ref("int_powerschool__terms") }}

        union all

        select
            _dbt_source_relation,
            schoolid,
            yearid,

            'Y1' as `quarter`,

            firstday as quarter_start_date,
            lastday as quarter_end_date,

            false as is_current_quarter,
            'S#' as semester,

        from {{ ref("stg_powerschool__terms") }}
        where isyearrec = 1
    ),

    student_roster as (
        select
            enr._dbt_source_relation,
            enr.studentid,
            enr.student_number,
            enr.student_name,
            enr.enroll_status,
            enr.cohort,
            enr.graduation_year,
            enr.gender,
            enr.ethnicity,
            enr.academic_year,
            enr.academic_year_display,
            enr.yearid,
            enr.region,
            enr.school_level_alt as school_level,
            enr.schoolid,
            enr.school,
            enr.grade_level,
            enr.advisory,
            enr.year_in_school,
            enr.year_in_network,
            enr.rn_undergrad,
            enr.is_self_contained as is_pathways,
            enr.is_out_of_district,
            enr.is_retained_year,
            enr.is_retained_ever,
            enr.student_slideback,
            enr.lunch_status,
            enr.lep_status,
            enr.gifted_and_talented,
            enr.iep_status,
            enr.is_504,
            enr.salesforce_id,
            enr.ktc_cohort,
            enr.is_counseling_services,
            enr.is_student_athlete,
            enr.ada,
            enr.ada_above_or_at_80,
            enr.hos,
            enr.school_leader,
            enr.school_leader_tableau_username,

            term.quarter,
            term.quarter_start_date,
            term.quarter_end_date,
            term.is_current_quarter,
            term.semester,

            gtq.gpa_semester,
            gtq.total_credit_hours_y1 as gpa_total_credit_hours,
            gtq.n_failing_y1 as gpa_n_failing_y1,

            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.cumulative_y1_gpa_projected_unweighted,
            gc.cumulative_y1_gpa_projected_s1,
            gc.cumulative_y1_gpa_projected_s1_unweighted,
            gc.core_cumulative_y1_gpa,
            gc.potential_gpa_credits_cum_projected,
            gc.potential_gpa_credits_current_year,
            gc.gpa_needed_for_cumulative_3_0,
            gc.is_cumulative_3_0_attainable,

            lb.gpa_y1_1_week_prior,
            lb.gpa_y1_2_week_prior,
            lb.gpa_y1_4_week_prior,
            lb.gpa_y1_unweighted_1_week_prior,
            lb.gpa_y1_unweighted_2_week_prior,
            lb.gpa_y1_unweighted_4_week_prior,
            lb.n_failing_y1_1_week_prior,
            lb.n_failing_y1_2_week_prior,
            lb.n_failing_y1_4_week_prior,

            enr.academic_year
            = {{ var("current_academic_year") }} as is_current_academic_year,

            if(
                term.quarter = 'Y1', gty.gpa_y1_unweighted, gtq.gpa_y1_unweighted
            ) as gpa_y1_unweighted,

            if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_term) as gpa_for_quarter,

            if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_y1) as gpa_y1,

        from {{ ref("int_extracts__student_enrollments") }} as enr
        inner join
            term
            on enr.schoolid = term.schoolid
            and enr.yearid = term.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="term") }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gtq
            on enr.studentid = gtq.studentid
            and enr.yearid = gtq.yearid
            and enr.schoolid = gtq.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gtq") }}
            and term.quarter = gtq.term_name
            and {{ union_dataset_join_clause(left_alias="term", right_alias="gtq") }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gty
            on enr.studentid = gty.studentid
            and enr.yearid = gty.yearid
            and enr.schoolid = gty.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gty") }}
            and gty.is_current
        /* gc join gated to the current year in ON: prior-year rows keep NULL
           cumulative/needed columns (as-of-today measures) */
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on enr.studentid = gc.studentid
            and enr.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gc") }}
            and enr.academic_year = {{ var("current_academic_year") }}
        /* lookback is current-year only by construction (yearid in the join
           key), so prior-year rows read NULL naturally */
        left join
            {{ ref("int_powerschool__gpa_term_lookback") }} as lb
            on enr.studentid = lb.studentid
            and enr.schoolid = lb.schoolid
            and enr.yearid = lb.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="lb") }}
        where
            enr.rn_year = 1
            and not enr.is_out_of_district
            and enr.enroll_status != -1
            and enr.academic_year >= {{ var("current_academic_year") - 1 }}
            /* Miami hard-excluded: region unsupported in the rebuilt
               dashboard (#4340) */
            -- TODO(#4340): add Paterson once PS gradebook data is populated
            and enr.region in ('Newark', 'Camden')
    ),

    course_enrollments as (
        select
            m._dbt_source_relation,
            m.cc_studentid as studentid,
            m.cc_yearid as yearid,
            m.cc_course_number as course_number,
            m.cc_sectionid as sectionid,
            m.cc_dateenrolled as date_enrolled,
            m.sections_dcid,
            m.sections_section_number as section_number,
            m.sections_external_expression as external_expression,
            m.courses_credittype as credit_type,
            m.courses_course_name as course_name,
            m.courses_excludefromgpa as exclude_from_gpa,
            m.teachernumber as teacher_number,
            m.teacher_lastfirst as teacher_name,

            f.is_tutoring as tutoring_nj,
            f.nj_student_tier,

            r.sam_account_name as teacher_tableau_username,
        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("int_extracts__student_enrollments_subjects") }} as f
            on m.cc_studentid = f.studentid
            and m.cc_academic_year = f.academic_year
            and m.courses_credittype = f.powerschool_credittype
            and {{ union_dataset_join_clause(left_alias="m", right_alias="f") }}
            and f.rn_year = 1
        left join
            {{ ref("int_people__staff_roster") }} as r
            on m.teachernumber = r.powerschool_teacher_number
        where
            m.rn_course_number_year = 1
            and m.cc_sectionid > 0
            and m.cc_course_number not in (
                'LOG100',  -- Lunch
                'LOG1010',  -- Lunch
                'LOG11',  -- Lunch
                'LOG12',  -- Lunch
                'LOG20',  -- Early Dismissal
                'LOG22999XL',  -- Lunch
                'LOG300',  -- Study Hall
                'LOG9',  -- Lunch
                'SEM22106G1',  -- Advisory
                'SEM22106S1'  -- Not in SY24-25 yet
            )
    ),

    y1_final_grades as (
        select
            _dbt_source_relation,
            studentid,
            yearid,
            course_number,
            storecode,

            cast(`percent` as float64) as y1_course_final_percent_grade_adjusted,

            grade as y1_course_final_letter_grade_adjusted,
            earnedcrhrs as y1_course_final_earned_credits,
            potentialcrhrs as y1_course_final_potential_credit_hours,
            gpa_points as y1_course_final_grade_points,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1' and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    quarter_grades as (
        /* current year: live gradebook */
        select
            _dbt_source_relation,
            studentid,
            yearid,
            course_number,

            storecode as `quarter`,

            term_percent_grade_adjusted as quarter_course_percent_grade,
            term_letter_grade_adjusted as quarter_course_letter_grade,
            term_grade_points as quarter_course_grade_points,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and not is_dropped_section
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')

        union all

        /* current year: in-progress Y1 row */
        select
            _dbt_source_relation,
            studentid,
            yearid,
            course_number,

            'Y1' as `quarter`,

            y1_percent_grade_adjusted as quarter_course_percent_grade,
            y1_letter_grade_adjusted as quarter_course_letter_grade,
            y1_grade_points as quarter_course_grade_points,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and termbin_is_current
            and not is_dropped_section

        union all

        /* prior year: stored grades (Q1-Q4 term rows plus the stored Y1 row,
           which fills the quarter columns on Y1 rows like the in-progress
           branch does for the current year) */
        select
            _dbt_source_relation,
            studentid,
            yearid,
            course_number,

            storecode as `quarter`,

            cast(`percent` as float64) as quarter_course_percent_grade,
            grade as quarter_course_letter_grade,
            gpa_points as quarter_course_grade_points,

            cast(null as float64) as y1_course_in_progress_percent_grade_adjusted,
            cast(null as string) as y1_course_in_progress_letter_grade_adjusted,
            cast(null as float64) as y1_course_in_progress_grade_points,
            cast(null as float64) as y1_course_in_progress_grade_points_unweighted,

            cast(null as float64) as need_60,
            cast(null as float64) as need_70,
            cast(null as float64) as need_80,
            cast(null as float64) as need_90,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode in ('Q1', 'Q2', 'Q3', 'Q4', 'Y1')
            and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    category_grades as (
        select
            _dbt_source_relation,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            storecode_type as category_name_code,
            storecode as category_quarter_code,
            percent_grade as category_quarter_percent_grade,
            percent_grade_y1_running as category_y1_percent_grade_running,

            concat('Q', storecode_order) as term,

            avg(if(is_current, percent_grade_y1_running, null)) over (
                partition by
                    _dbt_source_relation,
                    studentid,
                    yearid,
                    course_number,
                    storecode_type
            ) as category_y1_percent_grade_current,

            round(
                avg(percent_grade) over (
                    partition by _dbt_source_relation, yearid, studentid, storecode
                ),
                2
            ) as category_quarter_average_all_courses,

        from {{ ref("int_powerschool__category_grades") }}
        where
            yearid >= {{ var("current_academic_year") - 1991 }}
            and not is_dropped_section
            and storecode_type not in ('Q')
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.graduation_year,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.hos,
    s.school_leader,
    s.school_leader_tableau_username,
    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_pathways,
    s.is_retained_year,
    s.is_retained_ever,
    s.student_slideback,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.ada,
    s.ada_above_or_at_80,

    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,
    s.is_current_academic_year,

    s.gpa_for_quarter,
    s.gpa_semester,
    s.gpa_y1,
    s.gpa_y1_unweighted,
    s.gpa_total_credit_hours,
    s.gpa_n_failing_y1,

    s.gpa_y1_1_week_prior,
    s.gpa_y1_2_week_prior,
    s.gpa_y1_4_week_prior,
    s.gpa_y1_unweighted_1_week_prior,
    s.gpa_y1_unweighted_2_week_prior,
    s.gpa_y1_unweighted_4_week_prior,
    s.n_failing_y1_1_week_prior,
    s.n_failing_y1_2_week_prior,
    s.n_failing_y1_4_week_prior,

    s.cumulative_y1_gpa,
    s.cumulative_y1_gpa_unweighted,
    s.cumulative_y1_gpa_projected,
    s.cumulative_y1_gpa_projected_unweighted,
    s.cumulative_y1_gpa_projected_s1,
    s.cumulative_y1_gpa_projected_s1_unweighted,
    s.core_cumulative_y1_gpa,
    s.potential_gpa_credits_cum_projected,
    s.potential_gpa_credits_current_year,
    s.gpa_needed_for_cumulative_3_0,
    s.is_cumulative_3_0_attainable,

    ce.sectionid,
    ce.sections_dcid,
    ce.section_number,
    ce.external_expression,
    ce.date_enrolled,
    ce.credit_type,
    ce.course_number,
    ce.course_name,
    ce.exclude_from_gpa,
    ce.teacher_number,
    ce.teacher_name,
    ce.teacher_tableau_username,
    ce.tutoring_nj,
    ce.nj_student_tier,

    y1f.y1_course_final_percent_grade_adjusted,
    y1f.y1_course_final_letter_grade_adjusted,
    y1f.y1_course_final_earned_credits,
    y1f.y1_course_final_potential_credit_hours,
    y1f.y1_course_final_grade_points,

    qg.quarter_course_percent_grade,
    qg.quarter_course_letter_grade,
    qg.quarter_course_grade_points,
    qg.y1_course_in_progress_percent_grade_adjusted,
    qg.y1_course_in_progress_letter_grade_adjusted,
    qg.y1_course_in_progress_grade_points,
    qg.y1_course_in_progress_grade_points_unweighted,
    qg.need_60,
    qg.need_70,
    qg.need_80,
    qg.need_90,

    c.category_name_code,
    c.category_quarter_code,
    c.category_quarter_percent_grade,
    c.category_y1_percent_grade_running,
    c.category_y1_percent_grade_current,
    c.category_quarter_average_all_courses,

    if(
        s.grade_level < 9, ce.section_number, ce.external_expression
    ) as section_or_period,

from student_roster as s
left join
    course_enrollments as ce
    on s.studentid = ce.studentid
    and s.yearid = ce.yearid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
left join
    y1_final_grades as y1f
    on s.studentid = y1f.studentid
    and s.yearid = y1f.yearid
    and s.`quarter` = y1f.storecode
    and {{ union_dataset_join_clause(left_alias="s", right_alias="y1f") }}
    and ce.course_number = y1f.course_number
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="y1f") }}
left join
    quarter_grades as qg
    on s.studentid = qg.studentid
    and s.yearid = qg.yearid
    and s.`quarter` = qg.`quarter`
    and {{ union_dataset_join_clause(left_alias="s", right_alias="qg") }}
    and ce.course_number = qg.course_number
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
left join
    category_grades as c
    on s.studentid = c.studentid
    and s.yearid = c.yearid
    and s.`quarter` = c.term
    and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
    and ce.sectionid = c.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="c") }}
where s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
