{{ config(materialized="table") }}

with
    metric_union as (
        /* K-8 Reading & Math */
        select
            layer,
            'Formative Assessments' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            discipline,

            null as numerator,
            null as denominator,
            is_mastery_running_int as metric_value,
        from {{ ref("int_topline__formative_assessment_weekly") }}
        cross join unnest(['GPA, ACT, SAT', 'K-8 Reading and Math']) as layer

        union all

        select
            'K-8 Reading and Math' as layer,
            'DIBELS PM Mastery' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            'ELA' as discipline,

            null as numerator,
            null as denominator,
            met_pm_round_overall_criteria as metric_value,
        from {{ ref("int_topline__dibels_pm_weekly") }}

        union all

        select
            'K-8 Reading and Math' as layer,
            'DIBELS PM Fidelity' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            'ELA' as discipline,

            null as numerator,
            null as denominator,
            completed_test_round_int as metric_value,
        from {{ ref("int_topline__dibels_pm_weekly") }}

        union all

        select
            layer,
            'i-Ready Diagnostic' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            discipline,

            null as numerator,
            null as denominator,
            is_proficient as metric_value,
        from {{ ref("int_topline__iready_diagnostic_weekly") }}
        cross join unnest(['GPA, ACT, SAT', 'K-8 Reading and Math']) as layer

        union all

        select
            'K-8 Reading and Math' as layer,
            'i-Ready Lessons' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            discipline,

            null as numerator,
            null as denominator,
            if(n_lessons_passed_week >= 2, 1, 0) as metric_value,
        from {{ ref("int_topline__iready_lessons_weekly") }}

        union all

        select
            'K-8 Reading and Math' as layer,
            'Star Diagnostic' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            discipline,

            null as numerator,
            null as denominator,
            is_state_benchmark_proficient_int as metric_value,
        from {{ ref("int_topline__star_assessment_weekly") }}

        union all

        select
            'K-8 Reading and Math' as layer,
            'State Assessments' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            discipline,

            null as numerator,
            null as denominator,
            is_proficient_int as metric_value,
        from {{ ref("int_topline__state_assessments_weekly") }}
        where region != 'Miami'

        union all

        select
            'K-8 Reading and Math' as layer,
            'State Assessments' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            discipline,

            null as numerator,
            null as denominator,
            is_proficient_int as metric_value,
        from {{ ref("int_topline__state_assessments_weekly") }}
        where region = 'Miami' and test_round = 'PM3'

        union all

        select
            'K-8 Reading and Math' as layer,
            'FAST' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            discipline,

            null as numerator,
            null as denominator,
            is_proficient_int as metric_value,
        from {{ ref("int_topline__state_assessments_weekly") }}
        where region = 'Miami'

        union all

        /* Attendance & Enrollment */
        select
            'Attendance and Enrollment' as layer,
            'Total Enrollment' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            if(is_enrolled_week, 1, 0) as metric_value,
        from {{ ref("int_extracts__student_enrollments_weeks") }}

        union all

        select
            'Attendance and Enrollment' as layer,
            'Successful Contacts' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            successful_comms_sum_running as numerator,
            required_comms_count_running as denominator,
            safe_divide(
                successful_comms_sum_running, required_comms_count_running
            ) as metric_value,
        from {{ ref("int_topline__attendance_contacts_weekly") }}

        union all

        select
            'Attendance and Enrollment' as layer,
            'Chronic Absenteeism Interventions' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            successful_call_count as numerator,
            total_anticipated_calls as denominator,
            pct_interventions_complete as metric_value,
        from {{ ref("int_topline__attendance_interventions_weekly") }}

        union all

        select
            'Attendance and Enrollment' as layer,
            'ADA' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            attendance_value_sum_running as numerator,
            membership_value_sum_running as denominator,
            ada_running as metric_value,
        from {{ ref("int_topline__ada_running_weekly") }}

        union all

        select
            'Attendance and Enrollment' as layer,
            'Truancy' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            if(absence_sum_running >= 50, 1, 0) as metric_value,
        from {{ ref("int_topline__ada_running_weekly") }}

        union all

        select
            'Attendance and Enrollment' as layer,
            'Chronic Absenteeism' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            if(ada_running <= 0.90, 1, 0) as metric_value,
        from {{ ref("int_topline__ada_running_weekly") }}

        union all

        /* GPA & ACT/SAT */
        select
            'GPA, ACT, SAT' as layer,
            'Highest ' || test_type as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            case
                when test_type = 'SAT' and score >= 1010
                then 1
                when test_type = 'PSAT NMSQT' and score >= 910
                then 1
                when test_type = 'PSAT 8/9' and score >= 860
                then 1
                else 0
            end as metric_value,
        from {{ ref("int_topline__college_entrance_exams_weekly") }}

        union all

        select
            'GPA, ACT, SAT' as layer,
            'Projected Unweighted Cumulative GPA' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            if(cumulative_y1_gpa_projected_unweighted >= 3.00, 1, 0) as metric_value,
        from {{ ref("int_topline__gpa_cumulative_weekly") }}

        union all

        select
            layer,
            'Weighted Y1 GPA' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            if(gpa_y1 >= 3.00, 1, 0) as metric_value,
        from {{ ref("int_topline__gpa_term_weekly") }}
        cross join unnest(['GPA, ACT, SAT', 'K-8 Reading and Math']) as layer

        union all

        /* Student & Family Experience */
        select
            'Student and Family Experience' as layer,
            'School Community Diagnostic' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            average_rating as metric_value,
        from {{ ref("int_topline__school_community_diagnostic_weekly") }}

        union all

        select
            'Student and Family Experience' as layer,
            'Suspensions' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            is_suspended_y1_all_running as metric_value,
        from {{ ref("int_topline__suspension_weekly") }}

        union all

        select
            'Student and Family Experience' as layer,
            'Quarterly Incentives' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            is_receiving_incentive as metric_value,
        from {{ ref("int_topline__deanslist_incentives_weekly") }}

        union all

        /* College Matriculation */
        select
            'College Matriculation' as layer,
            'BA Applied' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            if(is_submitted_ba, 1, 0) as metric_value,
        from {{ ref("int_topline__college_matriculation_weekly") }}

        union all

        select
            'College Matriculation' as layer,
            'BA Accepted' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            if(is_accepted_ba, 1, 0) as metric_value,
        from {{ ref("int_topline__college_matriculation_weekly") }}

        union all

        select
            'College Matriculation' as layer,
            'BA Matriculated' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            if(is_matriculated_ba, 1, 0) as metric_value,
        from {{ ref("int_topline__college_matriculation_weekly") }}

        union all

        select
            'College Matriculation' as layer,
            'BA Quality Bar' as indicator,
            student_number,
            academic_year,
            week_start_monday as term,
            null as discipline,

            null as numerator,
            null as denominator,
            is_submitted_quality_bar_4yr_int as metric_value,
        from {{ ref("int_topline__college_matriculation_weekly") }}
    )

select
    co.academic_year,
    co.student_number,
    co.studentid,
    co.student_name,
    co.grade_level,
    co.region,
    co.schoolid,
    co.school,
    co.iep_status,
    co.lep_status,
    co.is_504,
    co.year_in_network,
    co.is_retained_year,
    co.gender,
    co.ethnicity,
    co.entrydate,
    co.exitdate,
    co.is_enrolled_week,
    co.is_current_week_mon_sun as is_current_week,

    mu.layer,
    mu.indicator,
    mu.discipline,
    mu.term,
    mu.numerator,
    mu.denominator,
    mu.metric_value,

    null as target_value,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    metric_union as mu
    on co.student_number = mu.student_number
    and co.academic_year = mu.academic_year
    and co.week_start_monday = mu.term
where co.academic_year >= {{ var("current_academic_year") - 1 }}

union all

select
    co.academic_year,
    co.student_number,
    co.studentid,
    co.student_name,
    co.grade_level,
    co.region,
    co.schoolid,
    co.school,
    co.iep_status,
    co.lep_status,
    co.is_504,
    co.year_in_network,
    co.is_retained_year,
    co.gender,
    co.ethnicity,
    co.entrydate,
    co.exitdate,
    co.is_enrolled_week,
    co.is_current_week_mon_sun as is_current_week,

    mu.layer,
    'Budget Target' indicator,
    mu.discipline,
    mu.term,
    mu.numerator,
    mu.denominator,
    mu.metric_value,

    et.budget_target as target_value,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    metric_union as mu
    on co.student_number = mu.student_number
    and co.academic_year = mu.academic_year
    and co.week_start_monday = mu.term
    and mu.indicator = 'Total Enrollment'
left join
    {{ ref("stg_google_sheets__topline_enrollment_targets") }} as et
    on co.academic_year = et.academic_year
    and co.schoolid = et.schoolid
where co.academic_year >= {{ var("current_academic_year") - 1 }}

union all

select
    co.academic_year,
    co.student_number,
    co.studentid,
    co.student_name,
    co.grade_level,
    co.region,
    co.schoolid,
    co.school,
    co.iep_status,
    co.lep_status,
    co.is_504,
    co.year_in_network,
    co.is_retained_year,
    co.gender,
    co.ethnicity,
    co.entrydate,
    co.exitdate,
    co.is_enrolled_week,
    co.is_current_week_mon_sun as is_current_week,

    mu.layer,
    'Seat Target' as indicator,
    mu.discipline,
    mu.term,
    mu.numerator,
    mu.denominator,
    mu.metric_value,

    et.seat_target as target_value,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    metric_union as mu
    on co.student_number = mu.student_number
    and co.academic_year = mu.academic_year
    and co.week_start_monday = mu.term
    and mu.indicator = 'Total Enrollment'
left join
    {{ ref("stg_google_sheets__topline_enrollment_targets") }} as et
    on co.academic_year = et.academic_year
    and co.schoolid = et.schoolid
where co.academic_year >= {{ var("current_academic_year") - 1 }}
