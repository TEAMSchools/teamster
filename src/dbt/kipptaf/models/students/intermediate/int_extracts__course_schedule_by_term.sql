with
    section_quarters as (
        select
            s._dbt_source_project,
            s.terms_academic_year as academic_year,
            s.school_abbreviation as school,
            s.school_name,
            s.sections_dcid,
            s.sections_termid as termid,
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
            s.school_level,
            s.school_level_alt,

            t.term as `quarter`,
            t.semester,
            t.term_start_date as quarter_start_date,
            t.term_end_date as quarter_end_date,
            t.term_start_date_clamped as quarter_start_date_alt,
            t.term_end_date_clamped as quarter_end_date_alt,
            t.is_current_term as is_current_quarter,
            t.first_day_school_year,
            t.last_day_school_year,
            t.days_in_term as days_in_quarter,

            {{ extract_region("s") }} as region,

            cast(s.terms_academic_year as string)
            || '-'
            || right(
                cast(s.terms_academic_year + 1 as string), 2
            ) as academic_year_display,

            if(cx.ap_course_subject is not null, true, false) as is_ap_course,

            count(*) over (
                partition by s._dbt_source_project, s.sections_id
            ) as section_quarter_count,

        from {{ ref("int_students__course_sections") }} as s
        left join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
            on s.courses_dcid = cx.coursesdcid
            and s._dbt_source_project = cx._dbt_source_project
        inner join
            {{ ref("int_students__terms") }} as t
            on s.sections_schoolid = t.schoolid
            and s.terms_academic_year = t.academic_year
            and s._dbt_source_project = t._dbt_source_project
            and s.terms_firstday <= t.term_end_date
            and s.terms_lastday >= t.term_start_date
        where s.sections_no_of_students != 0 and t.days_in_term is not null
    )

select
    s.* except (section_quarter_count),

    r.employee_number as teacher_employee_number,
    r.sam_account_name as teacher_tableau_username,
    r.reports_to_employee_number as manager_employee_number,
    r.reports_to_formatted_name as manager_name,
    r.reports_to_sam_account_name as manager_tableau_username,

    l.head_of_school_preferred_name_lastfirst as hos,
    l.school_leader_preferred_name_lastfirst as school_leader,
    l.school_leader_sam_account_name as school_leader_tableau_username,

    concat(s.region, s.school_level) as region_school_level,

    concat(s.region, s.school_level_alt) as region_school_level_alt,

    -- array_to_string skips nulls, so a null external_expression yields the bare
    -- section_number rather than a null label
    if(
        s.school_level_alt = 'HS',
        array_to_string([s.external_expression, s.section_number], ' '),
        s.section_number
    ) as section_or_period,

from section_quarters as s
left join
    {{ ref("int_people__staff_roster") }} as r
    on s.teacher_number = r.powerschool_teacher_number
left join
    {{ ref("int_people__leadership_crosswalk") }} as l
    on s.schoolid = l.home_work_location_powerschool_school_id
-- excludes single-quarter PS term sections (trimester specials, short-term
-- sections); origin is the model's initial commit, no documented business
-- rationale beyond the mechanical description -- see reference doc before
-- assuming this is deliberate policy vs. inherited behavior
where s.section_quarter_count >= 2
