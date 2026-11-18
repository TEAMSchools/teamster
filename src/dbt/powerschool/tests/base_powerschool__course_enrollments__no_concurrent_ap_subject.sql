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
        from {{ ref("base_powerschool__course_enrollments") }} as ce
        inner join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
            on ce.courses_dcid = cx.coursesdcid
        where cx.ap_course_subject is not null and not ce.is_dropped_section
    )

select
    a.cc_studyear,
    a.ap_course_subject,
    a.cc_studentid,
    a.cc_course_number,
    a.cc_dateenrolled,
    a.cc_dateleft,

    b.cc_course_number as other_course_number,
    b.cc_dateenrolled as other_dateenrolled,
    b.cc_dateleft as other_dateleft,
from enrollments as a
inner join
    enrollments as b
    on a.cc_studyear = b.cc_studyear
    and a.ap_course_subject = b.ap_course_subject
    and a.cc_course_number < b.cc_course_number
    and a.cc_dateenrolled < b.cc_dateleft
    and a.cc_dateleft > b.cc_dateenrolled
