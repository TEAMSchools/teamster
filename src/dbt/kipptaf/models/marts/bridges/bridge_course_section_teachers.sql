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
