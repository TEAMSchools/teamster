with
    enrollments as (
        select
            _dbt_source_relation,
            cc_studyear,
            cc_course_number,
            cc_studentid,
            cc_dateenrolled,
            cc_dateleft,

            lag(cc_dateleft) over (
                partition by _dbt_source_relation, cc_studyear, cc_course_number
                order by cc_dateenrolled, cc_dateleft
            ) as prev_dateleft,
        from {{ ref("base_powerschool__course_enrollments") }}
    )

select
    _dbt_source_relation,
    cc_studyear,
    cc_course_number,
    cc_studentid,
    cc_dateenrolled,
    cc_dateleft,
    prev_dateleft,
from enrollments
where cc_dateenrolled < prev_dateleft
