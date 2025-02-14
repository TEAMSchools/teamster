with
    custom_schedule as (
        select
            c._dbt_source_relation,
            c.cc_academic_year,
            c.cc_schoolid,

            c.cc_studentid,
            c.students_student_number,
            c.cc_dateenrolled,
            c.cc_dateleft,

            c.courses_course_number,
            c.courses_course_name,
            c.sections_dcid,
            c.sections_id,
            c.sections_external_expression,

            c.is_dropped_course,
            c.is_dropped_section,

            c.ap_course_subject,
            c.is_ap_course,
            c.courses_isfitnesscourse,

            c.rn_credittype_year,
            c.rn_course_number_year,

            c.terms_lastday,

            x.sced_course_name,
            x.crdc_course_group,
            x.crdc_subject_group,
            x.crdc_ap_group,
            x.sced_code as sced_code_xwalk,

            g.grade,
            g.is_transfer_grade,

            coalesce(x.ap_tag, false) as ap_tag,

            concat(c.nces_subject_area, c.nces_course_id) as sced_code_courses,

            if(
                c.is_ap_course != coalesce(x.ap_tag, false), true, false
            ) as ap_tag_mismatch,

            if(grade like 'F%', false, true) as passed_course,

            if(
                c.courses_course_name like '%(DE)' and not c.is_ap_course, true, false
            ) as is_dual_enrollment,

            if(
                c.courses_course_name like '%(CR)'
                and g.schoolname = 'KIPP Summer School',
                true,
                false
            ) as is_credit_recovery,

            if(
                c.cc_dateenrolled <= '2023-10-02' and c.cc_dateleft >= '2023-10-02',
                true,
                false
            ) as is_oct_01_course,

            if(c.cc_dateleft >= c.terms_lastday, true, false) as is_last_day_course,

        from {{ ref("base_powerschool__course_enrollments") }} as c
        left join
            {{ ref("stg_powerschool__storedgrades") }} as g
            on c.cc_academic_year = g.academic_year
            and c.sections_id = g.sectionid
            and c.cc_studentid = g.studentid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="g") }}
            and g.storecode = 'Y1'
        left join
            {{ ref("stg_crdc__sced_code_crosswalk") }} as x
            on concat(c.nces_subject_area, c.nces_course_id) = x.sced_code
        -- submission is always for the previous school year
        where
            c.cc_academic_year = {{ var("current_academic_year") - 1 }}
            and regexp_extract(c._dbt_source_relation, r'(kipp\w+)_') != 'kippmiami'

    )

-- this CTE is appending the different versions/groupings i need for reporting on
-- course data
select *, 'PENR-4' as crdc_question_section,
from custom_schedule
where is_dual_enrollment
