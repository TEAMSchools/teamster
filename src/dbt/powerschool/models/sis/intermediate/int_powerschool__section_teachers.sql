select
    sec.sections_dcid,
    sec.sections_id,
    sec.sections_schoolid,

    st.id as sectionteacher_id,
    st.teacherid,

    t.teachernumber,

    r.name as `role`,
    r.sortorder as role_sortorder,

    cast(st.start_date as date) as effective_start_date,
    cast(st.end_date as date) as effective_end_date,
from {{ ref("base_powerschool__sections") }} as sec
inner join
    {{ ref("stg_powerschool__sectionteacher") }} as st on sec.sections_id = st.sectionid
inner join
    {{ ref("int_powerschool__teachers") }} as t
    on st.teacherid = t.id
    and sec.sections_schoolid = t.schoolid
inner join {{ ref("stg_powerschool__roledef") }} as r on st.roleid = r.id
