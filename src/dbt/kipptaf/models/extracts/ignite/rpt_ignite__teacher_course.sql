with
    section_rows as (
        select
            academic_year,
            school_name,
            course_number,
            section_number,
            credit_type,
            course_name,
            section_or_period,
            student_number,

            cast(grade_level as string) as grade_level_string,
            cast(sectionid as string) as sectionid_string,
        from {{ ref("int_extracts__course_enrollments_by_term") }}
        where
            academic_year in ({{ var("ignite_academic_years") | join(", ") }})
            and grade_level in ({{ var("ignite_grade_levels") | join(", ") }})
            and region in ({{ "'" ~ (var("ignite_regions") | join("', '")) ~ "'" }})
    ),

    /* credit_type and course_name are constant within a section, so min() picks
     the same value every row would give. */
    section_detail as (
        select
            academic_year,
            school_name,
            course_number,
            section_number,

            min(credit_type) as credit_type,
            min(course_name) as course_name,
            min(sectionid_string) as classid,
            count(distinct student_number) as student_count,
            string_agg(
                distinct grade_level_string order by grade_level_string
            ) as grade_levels,
            string_agg(
                distinct section_or_period order by section_or_period
            ) as periods,
        from section_rows
        group by academic_year, school_name, course_number, section_number
    ),

    assembled as (
        select
            s.ref_id,
            s.school_name,
            s.academic_year,
            s.course_number,
            s.section_number,
            s.class_period,
            s.treatment_cp,
            s.treatment_rdc,
            s.treatment_rr,
            s.status,

            d.credit_type,
            d.course_name,
            d.classid,
            d.grade_levels,
            d.periods,
            d.student_count,
        from {{ ref("seed_ignite__treatment_sections") }} as s
        left join
            section_detail as d
            on s.academic_year = d.academic_year
            and s.school_name = d.school_name
            and s.course_number = d.course_number
            and s.section_number = d.section_number
    )

select
    ref_id,
    school_name,
    course_number,
    section_number,
    course_name,
    grade_levels,
    classid,
    student_count,
    status,

    class_period as reported_class_period,
    periods as powerschool_period,

    academic_year + 1 as school_year,

    coalesce(treatment_cp, 0) as cls_treatment_cp,
    coalesce(treatment_rdc, 0) as cls_treatment_rdc,
    coalesce(treatment_rr, 0) as cls_treatment_rr,

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
from assembled
