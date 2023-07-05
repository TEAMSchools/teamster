{%- set ref_sections = ref("stg_powerschool__sections") -%}
{%- set ref_courses = ref("stg_powerschool__courses") -%}

select
    {{ dbt_utils.star(from=ref_sections, relation_alias="sec", prefix="sections_") }},

    {{ dbt_utils.star(from=ref_courses, relation_alias="cou", prefix="courses_") }},

    t.teachernumber,
    t.lastfirst as teacher_lastfirst,
from {{ ref_sections }} as sec
inner join {{ ref_courses }} as cou on sec.course_number = cou.course_number
left join
    {{ ref("int_powerschool__teachers") }} as t
    on sec.teacher = t.id
    and sec.schoolid = t.schoolid
