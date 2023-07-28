{% set ref_cc = ref("stg_powerschool__cc") %}
{% set ref_sections = ref("base_powerschool__sections") %}

with
    sub as (
        select
            {{ dbt_utils.star(from=ref_cc, relation_alias="cc", prefix="cc_") }},

            {{ dbt_utils.star(from=ref_sections, relation_alias="sec") }},

            s.dcid as students_dcid,
            case
                when
                    cc.sectionid < 0
                    and s.enroll_status = 2
                    and s.exitdate = cc.dateleft
                then false
                when cc.sectionid < 0
                then true
                else false
            end as is_dropped_section,
        from {{ ref_cc }} as cc
        inner join {{ ref_sections }} as sec on cc.abs_sectionid = sec.sections_id
        inner join {{ ref("stg_powerschool__students") }} as s on cc.studentid = s.id
    )

select
    *,
    if(
        avg(if(is_dropped_section, 1, 0)) over (
            partition by cc_studyear, cc_course_number
        )
        = 1.0,
        true,
        false
    ) as is_dropped_course,
    row_number() over (
        partition by cc_studyear, courses_credittype
        order by cc_termid desc, cc_dateenrolled desc, cc_dateleft desc
    ) as rn_credittype_year,
    row_number() over (
        partition by cc_studyear, cc_course_number
        order by cc_termid desc, cc_dateenrolled desc, cc_dateleft desc
    ) as rn_course_number_year,
from sub
