-- Rationale lives in this test's tests/properties.yml description.
-- Any returned row is a failure.
with
    enrollments as (
        select
            ce.cc_studyear,
            ce.cc_studentid,
            ce.cc_course_number,
            ce.cc_dateenrolled,
            ce.cc_dateleft,

            cx.ap_course_subject,

            lag(ce.cc_course_number) over (
                partition by ce.cc_studyear, cx.ap_course_subject
                order by ce.cc_dateenrolled, ce.cc_dateleft
            ) as prev_course_number,

            lag(ce.cc_dateleft) over (
                partition by ce.cc_studyear, cx.ap_course_subject
                order by ce.cc_dateenrolled, ce.cc_dateleft
            ) as prev_dateleft,
        from {{ ref("base_powerschool__course_enrollments") }} as ce
        inner join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
            on ce.courses_dcid = cx.coursesdcid
        where cx.ap_course_subject is not null and not ce.is_dropped_section
    )

select
    cc_studyear,
    ap_course_subject,
    cc_studentid,
    cc_course_number,
    prev_course_number,
    cc_dateenrolled,
    cc_dateleft,
    prev_dateleft,
from enrollments
where cc_dateenrolled < prev_dateleft and cc_course_number != prev_course_number
