with
    cc_lag as (
        select
            _dbt_source_relation,
            studyear,
            course_number,
            dateleft,
            lag(dateleft) over (
                partition by _dbt_source_relation, studyear, course_number
                order by dateleft asc
            ) as dateleft_prev
        from {{ ref("stg_powerschool__cc") }}
    ),

    cc_overlap as (
        select _dbt_source_relation, studyear, course_number,
        from cc_lag
        where dateleft <= dateleft_prev
    )

select
    cc._dbt_source_relation,
    cc.cc_academic_year,
    cc.cc_course_number,
    cc.cc_dateenrolled,
    cc.cc_dateleft,
    cc.sections_section_number,
    cc.students_student_number,
from {{ ref("base_powerschool__course_enrollments") }} as cc
inner join
    cc_overlap as cco
    on cc.cc_studyear = cco.studyear
    and cc.cc_course_number = cco.course_number
    and {{ union_dataset_join_clause(left_alias="cc", right_alias="cco") }}
