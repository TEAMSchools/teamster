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
                partition_by="_dbt_source_project, academic_year, region, schoolid, `quarter`",
                order_by="quarter_start_date",
            )
        }}
    )

select
    s._dbt_source_project,
    s.terms_academic_year as academic_year,
    s.school_abbreviation as school,
    s.school_level,
    s.sections_dcid,
    s.sections_id as sectionid,
    s.sections_schoolid as schoolid,
    s.sections_course_number as course_number,
    s.sections_section_number as section_number,
    s.sections_external_expression as external_expression,
    s.courses_course_name as course_name,
    s.courses_credittype as credit_type,
    s.courses_excludefromgpa as exclude_from_gpa,
    s.sections_no_of_students,
    s.teachernumber as teacher_number,
    s.teacher_lastfirst as teacher_name,

    r.sam_account_name as teacher_tableau_username,
    r.reports_to_employee_number as manager_employee_number,
    r.reports_to_formatted_name as manager_name,
    r.reports_to_sam_account_name as manager_tableau_username,

    l.head_of_school_preferred_name_lastfirst as hos,
    l.school_leader_preferred_name_lastfirst as school_leader,
    l.school_leader_sam_account_name as school_leader_tableau_username,

    t.`quarter`,
    t.semester,
    t.quarter_start_date,
    t.quarter_end_date,
    t.quarter_start_date_alt,
    t.quarter_end_date_alt,
    t.is_current_quarter,
    t.days_in_quarter,

    initcap(regexp_extract(s._dbt_source_project, r'kipp(\w+)')) as region,

    if(
        s.school_name = 'KIPP Sumner Elementary' and s.sections_grade_level = 5,
        'MS',
        d.school_level
    ) as school_level_alt,

    cast(s.terms_academic_year as string)
    || '-'
    || right(cast(s.terms_academic_year + 1 as string), 2) as academic_year_display,

from {{ ref("base_powerschool__sections") }} as s
inner join
    {{ ref("stg_powerschool__schools") }} as d on s.sections_schoolid = d.school_number
left join
    {{ ref("int_people__staff_roster") }} as r
    on s.teachernumber = r.powerschool_teacher_number
left join
    {{ ref("int_people__leadership_crosswalk") }} as l
    on s.sections_schoolid = l.home_work_location_powerschool_school_id
inner join
    quarters as t
    on s.sections_schoolid = t.schoolid
    and s.terms_academic_year = t.academic_year
    and s._dbt_source_project = t._dbt_source_project
    and s.terms_firstday <= t.quarter_end_date
    and s.terms_lastday >= t.quarter_start_date
qualify count(*) over (partition by s._dbt_source_project, s.sections_id) >= 2
