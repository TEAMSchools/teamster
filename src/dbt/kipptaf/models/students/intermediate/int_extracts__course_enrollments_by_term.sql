with
    -- trunk-ignore(sqlfluff/ST03)
    actual_quarters as (
        select
            c._dbt_source_project,
            c.academic_year,
            c.region,
            c.schoolid,
            c.`quarter`,
            c.first_day_school_year,
            c.last_day_school_year,
            t.term_start_date as quarter_start_date,
            t.term_end_date as quarter_end_date,

            t.semester,
            t.is_current_term as is_current_quarter,

            if(
                c.`quarter` = 'Q1' and t.term_start_date < c.first_day_school_year,
                c.first_day_school_year,
                t.term_start_date
            ) as quarter_start_date_alt,

            if(
                c.`quarter` = 'Q4' and t.term_end_date > c.last_day_school_year,
                c.last_day_school_year,
                t.term_end_date
            ) as quarter_end_date_alt,

            sum(c.date_count) over (
                partition by
                    c._dbt_source_project,
                    c.academic_year,
                    c.region,
                    c.schoolid,
                    c.`quarter`
            ) as days_in_quarter,

        from {{ ref("int_powerschool__calendar_week") }} as c
        inner join
            {{ ref("int_powerschool__terms") }} as t
            on c.academic_year = t.academic_year
            and c.schoolid = t.schoolid
            and c._dbt_source_project = t._dbt_source_project
            and c.`quarter` = t.term
    ),

    quarters as (
        {{
            dbt_utils.deduplicate(
                relation="actual_quarters",
                partition_by="_dbt_source_project, academic_year, schoolid, `quarter`",
                order_by="quarter_start_date",
            )
        }}
    ),

    schedule_by_terms as (
        select
            e._dbt_source_project,
            e.cc_academic_year,
            e.cc_schoolid,
            e.cc_studentid,
            e.cc_dateenrolled as dateenrolled,
            e.cc_dateleft as dateleft,
            e.cc_sectionid as sectionid,
            e.cc_course_number as course_number,
            e.sections_dcid,
            e.sections_section_number as section_number,
            e.sections_external_expression as external_expression,
            e.courses_credittype as credit_type,
            e.courses_course_name as course_name,
            e.courses_excludefromgpa as exclude_from_gpa,
            e.sections_termid as termid,
            e.teachernumber as teacher_number,
            e.teacher_lastfirst as teacher_name,
            e.is_ap_course,

            q.`quarter`,
            q.semester,
            q.quarter_start_date,
            q.quarter_end_date,
            q.quarter_start_date_alt,
            q.quarter_end_date_alt,
            q.is_current_quarter,
            q.first_day_school_year,
            q.last_day_school_year,
            q.days_in_quarter,

            if(
                e.cc_dateenrolled < q.first_day_school_year,
                q.first_day_school_year,
                e.cc_dateenrolled
            ) as dateenrolled_alt,

            if(
                e.cc_dateleft > q.last_day_school_year,
                q.last_day_school_year,
                e.cc_dateleft
            ) as dateleft_alt,

        from {{ ref("base_powerschool__course_enrollments") }} as e
        inner join
            quarters as q
            on e.cc_academic_year = q.academic_year
            and e.cc_schoolid = q.schoolid
            and e._dbt_source_project = q._dbt_source_project
            and e.cc_dateenrolled <= q.quarter_end_date_alt
            and e.cc_dateleft >= q.quarter_start_date_alt
        where not e.is_dropped_section and e.sections_no_of_students != 0
    ),

    days_course_enrolled as (
        select
            s._dbt_source_project,
            s.cc_academic_year,
            s.cc_schoolid,
            s.cc_studentid,
            s.course_number,
            s.`quarter`,

            sum(c.date_count) as days_course_enrolled,

        from schedule_by_terms as s
        inner join
            {{ ref("int_powerschool__calendar_week") }} as c
            on s.cc_academic_year = c.academic_year
            and s.cc_schoolid = c.schoolid
            and s._dbt_source_project = c._dbt_source_project
            and s.`quarter` = c.`quarter`
            and s.dateenrolled_alt <= c.school_week_end_date
            and s.dateleft_alt >= c.school_week_start_date
        group by
            s._dbt_source_project,
            s.cc_academic_year,
            s.cc_schoolid,
            s.cc_studentid,
            s.course_number,
            s.`quarter`
    ),

    enrollments as (
        select
            e.*,

            s.sectionid,
            s.course_number,
            s.sections_dcid,
            s.section_number,
            s.external_expression,
            s.credit_type,
            s.course_name,
            s.exclude_from_gpa,
            s.termid,
            s.teacher_number,
            s.teacher_name,
            s.is_ap_course,
            s.`quarter`,
            s.semester,
            s.quarter_start_date,
            s.quarter_end_date,
            s.quarter_start_date_alt,
            s.quarter_end_date_alt,
            s.is_current_quarter,
            s.dateenrolled,
            s.dateleft,
            s.dateenrolled_alt,
            s.dateleft_alt,
            s.days_in_quarter,

            d.days_course_enrolled,

            if(
                e.school_level_alt = 'HS', s.external_expression, s.section_number
            ) as section_or_period,

            safe_divide(
                d.days_course_enrolled, s.days_in_quarter
            ) as pct_enrolled_in_quarter,

            row_number() over (
                partition by
                    s._dbt_source_project,
                    s.cc_academic_year,
                    s.cc_studentid,
                    s.course_number,
                    s.`quarter`
                order by e.exitdate desc, s.dateleft desc
            ) as rn,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            schedule_by_terms as s
            on e.academic_year = s.cc_academic_year
            and e.schoolid = s.cc_schoolid
            and e.studentid = s.cc_studentid
            and e._dbt_source_project = s._dbt_source_project
            and e.entrydate <= s.dateleft_alt
            and e.exitdate >= s.dateenrolled_alt
        left join
            days_course_enrolled as d
            on s.cc_academic_year = d.cc_academic_year
            and s.cc_schoolid = d.cc_schoolid
            and s.cc_studentid = d.cc_studentid
            and s.course_number = d.course_number
            and s.`quarter` = d.`quarter`
            and s._dbt_source_project = d._dbt_source_project
        where not e.is_pre_year_withdrawal
    )

select
    e.*,

    r.sam_account_name as teacher_tableau_username,
    r.reports_to_employee_number as manager_employee_number,
    r.reports_to_formatted_name as manager_name,
    r.reports_to_sam_account_name as manager_tableau_username,

    concat(e.region, e.school_level_alt) as region_school_level_alt,

from enrollments as e
left join
    {{ ref("int_people__staff_roster") }} as r
    on e.teacher_number = r.powerschool_teacher_number
where e.rn = 1
