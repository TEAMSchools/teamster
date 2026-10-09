with
    courses_below as (
        select
            studentid,
            _dbt_source_project,
            course_name,

            /* Y1 percents are whole numbers upstream, so no decimal is lost */
            format('%s %.0f', course_name, y1_percent_current) as course_label,
        from {{ ref("int_powerschool__course_pace") }}
        where is_below_target and not is_locked
    ),

    below_target as (
        select
            studentid,
            _dbt_source_project,

            string_agg(course_label, '; ' order by course_name) as courses_below_target,
        from courses_below
        group by studentid, _dbt_source_project
    ),

    quickest_win as (
        select
            studentid,
            _dbt_source_project,
            course_name as quickest_win_course,
            pace_percent_to_next as quickest_win_pace_percent,
            next_letter_grade as quickest_win_next_letter,
        from {{ ref("int_powerschool__course_pace") }}
        where quickest_win_rank = 1
    ),

    roster as (
        select
            co.academic_year_display,
            co.region,
            co.school,
            co.grade_level,
            co.team,
            co.student_number,
            co.student_name,
            co.salesforce_id,
            co.iep_status,
            co.gender,
            co.lep_status,
            co.is_504,
            co.gifted_and_talented,
            co.unweighted_ada,
            co.weighted_ada,
            co.is_hs_honors_program,

            term,

            y.gpa_y1,

            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected_unweighted,
            gc.cumulative_y1_gpa_projected_s1_unweighted,
            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_projected,

            gpa.gpa_term,

            t.pace_status,
            t.gpa_needed_unweighted,
            t.gpa_needed_weighted,
            t.target_letter_grade,
            t.target_cutoff_percent,
            t.n_courses_below_target,

            bt.courses_below_target,

            qw.quickest_win_course,
            qw.quickest_win_pace_percent,
            qw.quickest_win_next_letter,
        from {{ ref("int_extracts__student_enrollments") }} as co
        cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term
        left join
            {{ ref("int_powerschool__gpa_term") }} as y
            on co.studentid = y.studentid
            and co.yearid = y.yearid
            and y.is_current
            and co._dbt_source_project = y._dbt_source_project
        left join
            {{ ref("int_powerschool__gpa_term") }} as gpa
            on co.studentid = gpa.studentid
            and co.yearid = gpa.yearid
            and term = gpa.term_name
            and co._dbt_source_project = gpa._dbt_source_project
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on co.studentid = gc.studentid
            and co.schoolid = gc.schoolid
            and co._dbt_source_project = gc._dbt_source_project
        left join
            {{ ref("int_powerschool__student_y1_target") }} as t
            on co.studentid = t.studentid
            and co.schoolid = t.schoolid
            and co._dbt_source_project = t._dbt_source_project
        left join
            below_target as bt
            on co.studentid = bt.studentid
            and co._dbt_source_project = bt._dbt_source_project
        left join
            quickest_win as qw
            on co.studentid = qw.studentid
            and co._dbt_source_project = qw._dbt_source_project
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and co.enroll_status = 0
            and co.grade_level >= 5
    )

select
    academic_year_display as academic_year,
    region,
    student_name,
    student_number,
    school,
    grade_level,
    team,
    iep_status,
    gender,
    lep_status,
    gifted_and_talented,
    is_504,
    unweighted_ada,
    weighted_ada,

    gpa_q1,
    gpa_q2,
    gpa_q3,
    gpa_q4,

    gpa_y1,

    cumulative_y1_gpa_unweighted,
    cumulative_y1_gpa_projected_unweighted,
    cumulative_y1_gpa_projected_s1_unweighted,
    cumulative_y1_gpa,
    cumulative_y1_gpa_projected,

    pace_status,
    gpa_needed_unweighted,
    gpa_needed_weighted,
    target_letter_grade,
    target_cutoff_percent,
    n_courses_below_target,
    courses_below_target,
    quickest_win_course,
    quickest_win_pace_percent,
    quickest_win_next_letter,

    salesforce_id as salesforce_contact_id,
    is_hs_honors_program,
from roster pivot (max(gpa_term) as gpa for term in ('Q1', 'Q2', 'Q3', 'Q4'))
