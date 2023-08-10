with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

select
    ur.*,

    csc.illuminate_subject_area,
    csc.is_foundations,
    csc.is_advanced_math,

    row_number() over (
        partition by ur.cc_studyear, csc.illuminate_subject_area
        order by ur.cc_termid desc, ur.cc_dateenrolled desc, ur.cc_dateleft desc
    ) as rn_student_year_illuminate_subject_desc,
from union_relations as ur
left join
    {{ ref("stg_assessments__course_subject_crosswalk") }} as csc
    on ur.cc_course_number = csc.powerschool_course_number
