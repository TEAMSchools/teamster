with
    treated_sections as (
        select
            school_name,
            academic_year,
            course_number,
            section_number,
            treatment_cp,
            treatment_rdc,
            treatment_rr,
        from {{ ref("seed_ignite__treatment_sections") }}
        where status = 'resolved'
    ),

    enrollments as (
        select
            ce.student_number,
            ce.academic_year,
            ce.schoolid,
            ce.school_name,
            ce.course_number,
            ce.section_number,

            ts.treatment_cp,
            ts.treatment_rdc,
            ts.treatment_rr,
        from {{ ref("int_extracts__course_enrollments_by_term") }} as ce
        inner join
            treated_sections as ts
            on ce.academic_year = ts.academic_year
            and ce.school_name = ts.school_name
            and ce.course_number = ts.course_number
            and ce.section_number = ts.section_number
        where ce.student_number is not null
    )

/* grain projection: every selected column is functionally determined by
 (student_number, academic_year, course_number, section_number). The upstream is
 at student-course-term grain, so repeated terms for one section collapse. Not a
 mask for upstream duplicates. */
select distinct
    student_number,
    academic_year,
    schoolid,
    school_name,
    course_number,
    section_number,

    treatment_cp as cls_treatment_cp,
    treatment_rdc as cls_treatment_rdc,
    treatment_rr as cls_treatment_rr,
from enrollments
