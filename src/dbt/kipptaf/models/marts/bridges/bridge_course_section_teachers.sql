-- Focus, Miami's system of record from AY2026 forward, has no equivalent of
-- PowerSchool's sectionteacher table, so the PowerSchool branch below resolves
-- no teacher for a Miami section in those years. Focus models a single lead
-- teacher per course period, already resolved to the staff roster in
-- int_students__course_sections, so the Focus branch reads that resolved
-- teachernumber rather than re-deriving it.
--
-- Two Focus limitations, both source-data shape rather than modeling gaps:
--
-- * Lead teacher only. Focus carries co-teachers in stg_focus__co_teachers,
-- which is not surfaced into kipptaf, so the Co-teacher, Gradebook Access
-- and Blended Learning roles PowerSchool supplies have no Miami
-- counterpart from AY2026 forward.
-- * effective_start_date and effective_end_date are null. Focus attaches a
-- teacher to a course period without dating the assignment; inventing the
-- term dates would assert an assignment history the source does not
-- record.
--
-- 743 of Miami's 823 AY2026 sections resolve a lead teacher. The 80 that do
-- not are the documented Focus floor from #4972: 67 course periods with no
-- teacher assigned in Focus at all, plus 13 whose user resolves to no staff
-- roster row.
with
    -- The year boundary keeps the two branches disjoint. Miami's frozen
    -- PowerSchool archive still holds sectionteacher rows through AY2025, and
    -- those sections also carry a resolved teachernumber, so an unscoped Focus
    -- branch would emit a duplicate Lead Teacher row for every archive
    -- section. coalesce to 9999 fails toward emitting nothing rather than
    -- duplicating, when int_focus__schedule is empty in an unbuilt --defer dev
    -- copy.
    focus_academic_year_boundary as (
        select coalesce(min(academic_year), 9999) as min_academic_year,
        from {{ ref("int_focus__schedule") }}
    ),

    powerschool_teachers as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    ["sec.sections_dcid", "sec._dbt_source_project"]
                )
            }} as course_section_key,

            {{ dbt_utils.generate_surrogate_key(["sr.employee_number"]) }} as staff_key,

            r.name as `role`,

            cast(st.start_date as date) as effective_start_date,
            cast(st.end_date as date) as effective_end_date,

        from {{ ref("base_powerschool__sections") }} as sec
        inner join
            {{ ref("stg_powerschool__sectionteacher") }} as st
            on sec.sections_id = st.sectionid
            and sec._dbt_source_project = st._dbt_source_project
        inner join
            {{ ref("int_powerschool__teachers") }} as t
            on st.teacherid = t.id
            and sec.sections_schoolid = t.schoolid
            and st._dbt_source_project = t._dbt_source_project
        inner join
            {{ ref("stg_powerschool__roledef") }} as r
            on st.roleid = r.id
            and st._dbt_source_project = r._dbt_source_project
        inner join
            {{ ref("int_people__staff_roster") }} as sr
            on t.teachernumber = sr.powerschool_teacher_number
    ),

    focus_teachers as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    ["sec.sections_dcid", "sec._dbt_source_project"]
                )
            }} as course_section_key,

            {{ dbt_utils.generate_surrogate_key(["sr.employee_number"]) }} as staff_key,

            -- matches the stg_powerschool__roledef vocabulary so both branches
            -- share one role domain
            'Lead Teacher' as `role`,

            cast(null as date) as effective_start_date,
            cast(null as date) as effective_end_date,

        from {{ ref("base_powerschool__sections") }} as sec
        cross join focus_academic_year_boundary as fay
        inner join
            {{ ref("int_people__staff_roster") }} as sr
            on sec.teachernumber = sr.powerschool_teacher_number
        where
            sec._dbt_source_project = 'kippmiami'
            and sec.terms_academic_year >= fay.min_academic_year
    )

select *,
from powerschool_teachers

union all

select *,
from focus_teachers
