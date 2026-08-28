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
        -- cc_studyear is PowerSchool's student-year id and is null on every
        -- Focus row, so without this filter every Miami course collapses into
        -- one partition and the lag compares unrelated students. That stayed
        -- invisible while Focus left cc_dateleft null (the comparison was
        -- unknown); #5043 filled it, which turned the collapse into 18,491
        -- spurious results. Scope to rows that actually have the partition
        -- key. Partitioning on student_number + academic_year instead would
        -- cover both SIS branches -- worth doing, but it moves New Jersey.
        where cc_studyear is not null
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
