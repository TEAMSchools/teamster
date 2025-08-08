with
    term as (
        select
            _dbt_source_relation,
            schoolid,
            yearid,

            term as `quarter`,

            term_start_date as quarter_start_date,
            term_end_date as quarter_end_date,
            term_end_date as cal_quarter_end_date,

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
            lastday as cal_quarter_end_date,

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
            enr.gender,
            enr.ethnicity,
            enr.academic_year,
            enr.academic_year_display,
            enr.yearid,
            enr.region,
            enr.school_level,
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
            enr.lunch_status,
            enr.lep_status,
            enr.gifted_and_talented,
            enr.iep_status,
            enr.is_504,
            enr.salesforce_id,
            enr.ktc_cohort,
            enr.is_counseling_services,
            enr.is_student_athlete,
            enr.ada_above_or_at_80,

            term.`quarter`,
            term.quarter_start_date,
            term.quarter_end_date,
            term.cal_quarter_end_date,
            term.is_current_quarter,
            term.semester,

            leader.head_of_school_preferred_name_lastfirst as hos,
            leader.school_leader_preferred_name_lastfirst as school_leader,
            leader.school_leader_sam_account_name as school_leader_tableau_username,

            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.cumulative_y1_gpa_projected_s1,
            gc.cumulative_y1_gpa_projected_s1_unweighted,
            gc.core_cumulative_y1_gpa,

            gtq.gpa_semester,
            gtq.gpa_y1_unweighted,
            gtq.total_credit_hours_y1 as gpa_total_credit_hours,
            gtq.n_failing_y1 as gpa_n_failing_y1,

            round(enr.ada, 3) as ada,

            if(term.`quarter` = 'Y1', gty.gpa_y1, gtq.gpa_term) as gpa_for_quarter,

            if(term.`quarter` = 'Y1', gty.gpa_y1, gtq.gpa_y1) as gpa_y1,

        from {{ ref("int_extracts__student_enrollments") }} as enr
        inner join
            term
            on enr.schoolid = term.schoolid
            and enr.yearid = term.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="term") }}
        left join
            {{ ref("int_people__leadership_crosswalk") }} as leader
            on enr.schoolid = leader.home_work_location_powerschool_school_id
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on enr.studentid = gc.studentid
            and enr.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gc") }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gtq
            on enr.studentid = gtq.studentid
            and enr.yearid = gtq.yearid
            and enr.schoolid = gtq.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gtq") }}
            and term.`quarter` = gtq.term_name
            and {{ union_dataset_join_clause(left_alias="term", right_alias="gtq") }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gty
            on enr.studentid = gty.studentid
            and enr.yearid = gty.yearid
            and enr.schoolid = gty.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gty") }}
            and gty.is_current
        where enr.rn_year = 1 and not enr.is_out_of_district and enr.enroll_status != -1
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
            m.sections_termid as termid,
            m.courses_credittype as credit_type,
            m.courses_course_name as course_name,
            m.courses_excludefromgpa as exclude_from_gpa,
            m.teachernumber as teacher_number,
            m.teacher_lastfirst as teacher_name,

            f.is_tutoring as tutoring_nj,
            f.nj_student_tier,

        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("int_extracts__student_enrollments_subjects") }} as f
            on m.cc_studentid = f.studentid
            and m.cc_academic_year = f.academic_year
            and m.courses_credittype = f.powerschool_credittype
            and {{ union_dataset_join_clause(left_alias="m", right_alias="f") }}
            and f.rn_year = 1
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

    y1_historical as (
        select
            tr._dbt_source_relation,
            tr.studentid,
            tr.academic_year,
            tr.yearid,
            tr.schoolid,
            tr.schoolname,
            tr.grade_level,
            tr.course_name,
            tr.sectionid,
            tr.teacher_name,
            tr.storecode,
            tr.termid,
            tr.`percent` as y1_course_final_percent_grade_adjusted,
            tr.grade as y1_course_final_letter_grade_adjusted,
            tr.earnedcrhrs as y1_course_final_earned_credits,
            tr.potentialcrhrs as y1_course_final_potential_credit_hours,
            tr.gpa_points as y1_course_final_grade_points,
            tr.excludefromgpa,
            tr.is_transfer_grade,

            if(tr.is_transfer_grade, 'Transfer', tr.credit_type) as credit_type,

            if(
                tr.is_transfer_grade,
                concat(
                    'T',
                    upper(regexp_extract(tr._dbt_source_relation, r'(kipp\w+)_')),
                    tr.dcid
                ),
                tr.course_number
            ) as course_number,

            if(co.student_number is not null, true, false) as is_enrollment_matched,

        from {{ ref("stg_powerschool__storedgrades") }} as tr
        left join
            student_roster as co
            on tr.studentid = co.studentid
            and tr.academic_year = co.academic_year
            and tr.schoolid = co.schoolid
            and tr.storecode = co.`quarter`
            and {{ union_dataset_join_clause(left_alias="tr", right_alias="co") }}
        where tr.storecode = 'Y1'
    ),

    quarter_and_ip_y1_grades as (
        select
            _dbt_source_relation,
            studentid,
            yearid,
            schoolid,
            course_number,
            sectionid,
            termid,

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

            citizenship as quarter_citizenship,
            comment_value as quarter_comment_value,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and not is_dropped_section
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')

        union all

        select
            _dbt_source_relation,
            studentid,
            yearid,
            schoolid,
            course_number,
            sectionid,
            termid,

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

            null as quarter_citizenship,
            null as quarter_comment_value,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and termbin_is_current
            and not is_dropped_section
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
            yearid = {{ var("current_academic_year") - 1990 }}
            and not is_dropped_section
            and storecode_type not in ('Q', 'H')
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
    s.cal_quarter_end_date,
    s.is_current_quarter,

    s.gpa_for_quarter,
    s.gpa_semester,
    s.gpa_y1,
    s.gpa_y1_unweighted,
    s.gpa_total_credit_hours,
    s.gpa_n_failing_y1,

    s.cumulative_y1_gpa,
    s.cumulative_y1_gpa_unweighted,
    s.cumulative_y1_gpa_projected,
    s.cumulative_y1_gpa_projected_s1,
    s.cumulative_y1_gpa_projected_s1_unweighted,
    s.core_cumulative_y1_gpa,

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
    ce.tutoring_nj,
    ce.nj_student_tier,

    r.sam_account_name as teacher_tableau_username,

    y1h.y1_course_final_percent_grade_adjusted,
    y1h.y1_course_final_letter_grade_adjusted,
    y1h.y1_course_final_earned_credits,
    y1h.y1_course_final_potential_credit_hours,
    y1h.y1_course_final_grade_points,

    qy1.quarter_course_percent_grade,
    qy1.quarter_course_letter_grade,
    qy1.quarter_course_grade_points,

    qy1.y1_course_in_progress_percent_grade_adjusted,
    qy1.y1_course_in_progress_letter_grade_adjusted,
    qy1.y1_course_in_progress_grade_points,
    qy1.y1_course_in_progress_grade_points_unweighted,

    qy1.need_60,
    qy1.need_70,
    qy1.need_80,
    qy1.need_90,

    qy1.quarter_citizenship,
    qy1.quarter_comment_value,

    c.category_name_code,
    c.category_quarter_code,
    c.category_quarter_percent_grade,
    c.category_y1_percent_grade_running,
    c.category_y1_percent_grade_current,
    c.category_quarter_average_all_courses,

    'Local' as roster_type,

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
    {{ ref("int_people__staff_roster") }} as r
    on ce.teacher_number = r.powerschool_teacher_number
left join
    y1_historical as y1h
    on s.studentid = y1h.studentid
    and s.yearid = y1h.yearid
    and s.`quarter` = y1h.storecode
    and {{ union_dataset_join_clause(left_alias="s", right_alias="y1h") }}
    and ce.course_number = y1h.course_number
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="y1h") }}
left join
    quarter_and_ip_y1_grades as qy1
    on s.studentid = qy1.studentid
    and s.yearid = qy1.yearid
    and s.`quarter` = qy1.`quarter`
    and {{ union_dataset_join_clause(left_alias="s", right_alias="qy1") }}
    and ce.sectionid = qy1.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qy1") }}
left join
    category_grades as c
    on s.studentid = c.studentid
    and s.yearid = c.yearid
    and s.`quarter` = c.term
    and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
    and ce.sectionid = c.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="c") }}
where s.quarter_start_date <= current_date('{{ var("local_timezone") }}')

union all

select
    e1._dbt_source_relation,
    e1.academic_year,
    e1.academic_year_display,
    e1.region,
    e1.school_level,
    e1.schoolid,
    e1.school,
    e1.studentid,
    e1.student_number,
    e1.student_name,
    e1.grade_level,
    e1.salesforce_id,
    e1.ktc_cohort,
    e1.enroll_status,
    e1.cohort,
    e1.gender,
    e1.ethnicity,
    e1.advisory,
    e1.hos,
    e1.school_leader,
    e1.school_leader_tableau_username,
    e1.year_in_school,
    e1.year_in_network,
    e1.rn_undergrad,
    e1.is_out_of_district,
    e1.is_pathways,
    e1.is_retained_year,
    e1.is_retained_ever,
    e1.lunch_status,
    e1.gifted_and_talented,
    e1.iep_status,
    e1.lep_status,
    e1.is_504,
    e1.is_counseling_services,
    e1.is_student_athlete,
    e1.ada,
    e1.ada_above_or_at_80,

    e1.`quarter`,
    e1.semester,
    e1.quarter_start_date,
    e1.quarter_end_date,
    e1.cal_quarter_end_date,
    e1.is_current_quarter,

    e1.gpa_for_quarter,
    e1.gpa_semester,
    e1.gpa_y1,
    e1.gpa_y1_unweighted,
    e1.gpa_total_credit_hours,
    e1.gpa_n_failing_y1,

    e1.cumulative_y1_gpa,
    e1.cumulative_y1_gpa_unweighted,
    e1.cumulative_y1_gpa_projected,
    e1.cumulative_y1_gpa_projected_s1,
    e1.cumulative_y1_gpa_projected_s1_unweighted,
    e1.core_cumulative_y1_gpa,

    null as sectionid,
    null as sections_dcid,
    null as section_number,
    null as external_expression,
    null as date_enrolled,

    y1h.credit_type,
    y1h.course_number,
    y1h.course_name,
    y1h.excludefromgpa as exclude_from_gpa,

    null as teacher_number,

    y1h.teacher_name,

    null as tutoring_nj,
    null as nj_student_tier,
    null as teacher_tableau_username,

    y1h.y1_course_final_percent_grade_adjusted,
    y1h.y1_course_final_letter_grade_adjusted,
    y1h.y1_course_final_earned_credits,
    y1h.y1_course_final_potential_credit_hours,
    y1h.y1_course_final_grade_points,

    null as quarter_course_percent_grade,
    null as quarter_course_letter_grade,
    null as quarter_course_grade_points,
    null as y1_course_in_progress_percent_grade_adjusted,
    null as y1_course_in_progress_letter_grade_adjusted,
    null as y1_course_in_progress_grade_points,
    null as y1_course_in_progress_grade_points_unweighted,

    null as need_60,
    null as need_70,
    null as need_80,
    null as need_90,

    null as quarter_citizenship,
    null as quarter_comment_value,

    null as category_name_code,
    null as category_quarter_code,
    null as category_quarter_percent_grade,
    null as category_y1_percent_grade_running,
    null as category_y1_percent_grade_current,
    null as category_quarter_average_all_courses,

    'Transfer' as roster_type,

    null as section_or_period,

from y1_historical as y1h
inner join
    student_roster as e1
    on y1h.studentid = e1.studentid
    and y1h.schoolid = e1.schoolid
    and y1h.storecode = e1.`quarter`
    and {{ union_dataset_join_clause(left_alias="y1h", right_alias="e1") }}
    and e1.year_in_school = 1
where y1h.is_transfer_grade and not y1h.is_enrollment_matched
