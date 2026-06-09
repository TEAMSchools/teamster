with
    teacher_master_schedule as (
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
            s.teachernumber as teacher_number,
            s.teacher_lastfirst as teacher_name,

            r.sam_account_name as teacher_tableau_username,
            r.reports_to_employee_number as manager_employee_number,
            r.reports_to_formatted_name as manager_name,
            r.reports_to_sam_account_name as manager_tableau_username,

            l.head_of_school_preferred_name_lastfirst as hos,
            l.school_leader_preferred_name_lastfirst as school_leader,
            l.school_leader_sam_account_name as school_leader_tableau_username,

            t.yearid,
            t.term as `quarter`,
            t.semester,
            t.term_start_date as quarter_start_date,
            t.term_end_date as quarter_end_date,
            t.is_current_term,

            initcap(regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')) as region,

            if(
                s.school_name = 'KIPP Sumner Elementary' and s.sections_grade_level = 5,
                'MS',
                null
            ) as school_level_alt,

            cast(s.terms_academic_year as string)
            || '-'
            || right(
                cast(s.terms_academic_year + 1 as string), 2
            ) as academic_year_display,

        from {{ ref("base_powerschool__sections") }} as s
        left join
            {{ ref("int_people__staff_roster") }} as r
            on s.teachernumber = r.powerschool_teacher_number
        left join
            {{ ref("int_people__leadership_crosswalk") }} as l
            on s.sections_schoolid = l.home_work_location_powerschool_school_id
        inner join
            {{ ref("int_powerschool__terms") }} as t
            on s.sections_schoolid = t.schoolid
            and s.terms_yearid = t.yearid
            and s._dbt_source_project = t._dbt_source_project
        where
            s.terms_academic_year = {{ var("current_academic_year") }}
            and s.sections_no_of_students != 0
    )

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.yearid,
    s.schoolid,
    s.school,
    s.region,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.teacher_tableau_username,
    s.manager_employee_number,
    s.manager_name,
    s.manager_tableau_username,
    s.hos,
    s.school_leader,
    s.school_leader_tableau_username,
    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_term,

    null as assignment_category_code,
    null as assignment_category_name,
    null as assignment_category_term,
    null as expectation,
    null as notes,

    coalesce(s.school_level_alt, s.school_level) as school_level,

    concat(
        s.region, coalesce(s.school_level_alt, s.school_level)
    ) as region_school_level,

    if(
        coalesce(s.school_level_alt, s.school_level) = 'HS',
        s.external_expression,
        s.section_number
    ) as section_or_period,

    'teacher_scaffold' as scaffold_name,

from teacher_master_schedule as s

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.yearid,
    s.schoolid,
    s.school,
    s.region,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.teacher_tableau_username,
    s.manager_employee_number,
    s.manager_name,
    s.manager_tableau_username,
    s.hos,
    s.school_leader,
    s.school_leader_tableau_username,
    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_term,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    coalesce(s.school_level_alt, s.school_level) as school_level,

    concat(
        s.region, coalesce(s.school_level_alt, s.school_level)
    ) as region_school_level,

    if(
        coalesce(s.school_level_alt, s.school_level) = 'HS',
        s.external_expression,
        s.section_number
    ) as section_or_period,

    'teacher_category_scaffold' as scaffold_name,

from teacher_master_schedule as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
