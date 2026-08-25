with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "base_powerschool__sections"),
                    source("kippcamden_powerschool", "base_powerschool__sections"),
                    source("kippmiami_powerschool", "base_powerschool__sections"),
                    source("kipppaterson_powerschool", "base_powerschool__sections"),
                ]
            )
        }}
    ),

    sections as (
        select *, {{ extract_source_project() }} as _dbt_source_project,
        from union_relations
    ),

    -- Focus is Miami's system of record from AY2026 forward, but the frozen
    -- archive still holds Miami AY2020 through AY2025. Scope by year rather
    -- than excluding Miami wholesale, and derive the boundary so a Focus
    -- backfill of an earlier year does not silently double-count.
    focus_academic_year_boundary as (
        select min(academic_year) as min_academic_year,
        from {{ ref("int_focus__schedule") }}
    ),

    powerschool_conformed as (
        select
            sec.*,

            if(cx.ap_course_subject is not null, true, false) as is_ap_course,

            coalesce(sec.sections_course_number like 'HR%', false) as is_homeroom,
        from sections as sec
        cross join focus_academic_year_boundary as fay
        left join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
            on sec.courses_dcid = cx.coursesdcid
            and sec._dbt_source_project = cx._dbt_source_project
        where
            not (
                sec._dbt_source_project = 'kippmiami'
                and sec.terms_academic_year >= fay.min_academic_year
            )
    ),

    focus_conformed as (
        select
            cp.course_period_id as sections_dcid,
            cp.course_period_id as sections_id,
            cp.course_id as courses_dcid,
            cp.syear as terms_academic_year,
            cp.short_name as sections_section_number,
            loc.powerschool_school_id as sections_schoolid,
            c.short_name as sections_course_number,
            sr.powerschool_teacher_number as teachernumber,

            'kippmiami' as _dbt_source_project,

            -- Focus carries a homeroom boolean on both the course and the
            -- course period and it is null on every row, so the homeroom
            -- course is identified by title. Same rule int_focus__advisory
            -- already uses. Elementary-only coverage is Focus configuration,
            -- tracked on #4868.
            coalesce(c.title like 'Homeroom%', false) as is_homeroom,

            -- The AP course subject crosswalk is a New Jersey state
            -- reporting table. Miami is Florida, so this is correctly absent
            -- rather than deferred -- no tracking issue.
            cast(null as bool) as is_ap_course,
        from {{ ref("int_focus__course_periods") }} as cp
        inner join {{ ref("int_focus__courses") }} as c on cp.course_id = c.course_id
        inner join {{ ref("int_focus__schools") }} as sch on cp.school_id = sch.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on sch.school_number = loc.focus_school_id
        left join {{ ref("int_focus__users") }} as usr on cp.teacher_id = usr.staff_id
        left join
            {{ ref("int_people__staff_roster") }} as sr
            on safe_cast(usr.ein as int64) = sr.employee_number
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
