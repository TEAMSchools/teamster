with
    enrollment_terms as (
        select
            student_number,
            studentid,
            academic_year,
            schoolid,
            course_number,
            section_number,
            sectionid,
            section_or_period,
            course_name,
            credit_type,
            grade_level,
            is_self_contained,
            semester,
        from {{ ref("int_extracts__course_enrollments_by_term") }}
        where
            academic_year in ({{ var("ignite_academic_years") | join(", ") }})
            and grade_level in ({{ var("ignite_grade_levels") | join(", ") }})
            and region in ({{ "'" ~ (var("ignite_regions") | join("', '")) ~ "'" }})
            and credit_type in ('ENG', 'MATH', 'SCI', 'SOC')
            and student_number is not null
    ),

    /* A section spanning both semesters is a year-long course, for which
     Mathematica's fall/spring semester field does not apply and is left null. */
    section_span as (
        select
            student_number,
            academic_year,
            course_number,
            section_number,
            count(distinct semester) as semester_count,
            min(semester) as first_semester,
        from enrollment_terms
        group by student_number, academic_year, course_number, section_number
    ),

    /* grain projection: the upstream is student-course-term grain and every
     column here is functionally determined by (student_number, academic_year,
     course_number, section_number). Not a mask for upstream duplicates. */
    enrollments as (
        select distinct
            student_number,
            studentid,
            academic_year,
            schoolid,
            course_number,
            section_number,
            sectionid,
            section_or_period,
            course_name,
            credit_type,
            grade_level,
            is_self_contained,
        from enrollment_terms
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    year_grades as (
        select studentid, sectionid, academic_year, grade, percent,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1'
            and not is_transfer_grade
            and academic_year in ({{ var("ignite_academic_years") | join(", ") }})
    ),

    /* TODO: one student-section-year carries seven non-transfer Y1 grade rows
     upstream. Deduplicate so the outbound file holds one row per student per
     course; the highest percent wins. */
    course_grades as (
        {{
            dbt_utils.deduplicate(
                relation="year_grades",
                partition_by="studentid, sectionid, academic_year",
                order_by="percent desc",
            )
        }}
    ),

    student_treatment as (
        select
            student_number,
            academic_year,
            max(cls_treatment_cp) as treatment_cp,
            max(cls_treatment_rdc) as treatment_rdc,
            max(cls_treatment_rr) as treatment_rr,
        from {{ ref("int_ignite__treatment_assignment") }}
        group by student_number, academic_year
    ),

    assembled as (
        select
            e.academic_year,
            e.course_number,
            e.section_number,
            e.section_or_period,
            e.course_name,
            e.credit_type,
            e.grade_level,
            e.is_self_contained,
            e.sectionid,

            x.stu_id,

            n.nces_school_id,

            s.semester_count,
            s.first_semester,

            g.grade,

            t.cls_treatment_cp,
            t.cls_treatment_rdc,
            t.cls_treatment_rr,

            st.treatment_cp,
            st.treatment_rdc,
            st.treatment_rr,
        from enrollments as e
        inner join
            {{ ref("int_ignite__student_id_crosswalk") }} as x
            on e.student_number = x.student_number
        left join
            {{ ref("seed_ignite__school_nces_ids") }} as n on e.schoolid = n.schoolid
        left join
            section_span as s
            on e.student_number = s.student_number
            and e.academic_year = s.academic_year
            and e.course_number = s.course_number
            and e.section_number = s.section_number
        left join
            course_grades as g
            on e.studentid = g.studentid
            and e.sectionid = g.sectionid
            and e.academic_year = g.academic_year
        left join
            {{ ref("int_ignite__treatment_assignment") }} as t
            on e.student_number = t.student_number
            and e.academic_year = t.academic_year
            and e.course_number = t.course_number
            and e.section_number = t.section_number
        left join
            student_treatment as st
            on e.student_number = st.student_number
            and e.academic_year = st.academic_year
    ),

    graded as (
        select
            academic_year,
            course_number,
            section_number,
            course_name,
            grade_level,
            stu_id,
            nces_school_id,
            semester_count,
            first_semester,
            cls_treatment_cp,
            cls_treatment_rdc,
            cls_treatment_rr,
            treatment_cp,
            treatment_rdc,
            treatment_rr,

            cast(sectionid as string) as classid,
            cast(section_or_period as string) as course_period,

            left(grade, 1) as course_grade,

            if(is_self_contained, 1, 0) as course_selfcont,

            case
                credit_type
                when 'ENG'
                then 'English'
                when 'MATH'
                then 'Mathematics'
                when 'SCI'
                then 'Science'
                when 'SOC'
                then 'History'
            end as subject,

            case
                when semester_count > 1
                then null
                when first_semester = 'S1'
                then 1
                when first_semester = 'S2'
                then 2
            end as semester,
        from assembled
    )

select
    stu_id,
    course_number,
    section_number,
    course_period,
    subject,
    grade_level,
    semester,
    course_name,
    course_selfcont,
    course_grade,
    classid,

    nces_school_id as school_id,

    academic_year + 1 as school_year,

    coalesce(treatment_cp, 0) as treatment_cp,
    coalesce(treatment_rdc, 0) as treatment_rdc,
    coalesce(treatment_rr, 0) as treatment_rr,
    coalesce(cls_treatment_cp, 0) as cls_treatment_cp,
    coalesce(cls_treatment_rdc, 0) as cls_treatment_rdc,
    coalesce(cls_treatment_rr, 0) as cls_treatment_rr,

    case
        when course_grade is null
        then null
        when course_grade in ('A', 'B', 'C', 'D')
        then 1
        else 0
    end as passed,
    case
        when course_grade is null
        then null
        when course_grade in ('A', 'B', 'C')
        then 1
        else 0
    end as passed_c,
from graded
