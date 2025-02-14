with
    retained as (
        -- reason for distinct: for students with multiple enrollments
        select distinct student_number, is_retained_year,
        from {{ ref("base_powerschool__student_enrollments") }}
        where
            -- submission is always for the previous school year, but retention is
            -- tracked only on the submission year + 1 (current academic year)
            academic_year = {{ var("current_academic_year") }}
            and grade_level != 99
            and is_retained_year
            -- miami does their own submission
            and region != 'Miami'
    ),

    enrollment as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.schoolid,
            e.school_abbreviation,

            e.studentid,
            e.student_number,
            e.grade_level,
            e.entrydate,
            e.exitdate,
            e.enroll_status,

            e.rn_year,
            e.is_enrolled_oct01,

            e.gender,
            e.ethnicity,
            e.gifted_and_talented,
            e.is_504,
            e.lep_status,

            adb.contact_id,

            coalesce(r.is_retained_year, false) as is_retained_year,

            if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

            if(e.spedlep like 'SPED%' and not is_504, true, false) as iep_only,

            if(e.spedlep like 'SPED%' and is_504, true, false) as iep_and_c504,

            if(e.spedlep not like 'SPED%' and is_504, true, false) as c504_only,

        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        left join retained as r on e.student_number = r.student_number
        where
            -- submission is always for the previous school year
            e.academic_year = {{ var("current_academic_year") - 1 }}
            and e.grade_level != 99
            -- miami does their own submission
            and e.region != 'Miami'
    ),

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
            -- miami does their own submission
            and regexp_extract(c._dbt_source_relation, r'(kipp\w+)_') != 'kippmiami'

    ),

    -- this CTE is appending the different versions/groupings i need for reporting on
    -- course data
    -- dual enrolled students
    final_schedule as (
        select *, 'PENR-4' as crdc_question_section,
        from custom_schedule
        where is_dual_enrollment

        union all

        -- credit recovery students
        select *, 'PENR-6' as crdc_question_section,
        from custom_schedule
        where is_credit_recovery

        union all

        -- algebra classes for MS; we dont' do geometry, so there will be no cte check
        -- for it
        select *, 'COUR-1' as crdc_question_section,
        from custom_schedule
        -- alg 1 ms courses use a special code
        where sced_code_courses = '52052'

        union all

        -- hs math courses
        select *, 'COUR-7' as crdc_question_section,
        from custom_schedule
        where
            crdc_subject_group in (
                'Algebra I',
                'Geometry',
                'Algebra II',
                'Advanced Mathematics',
                'Calculus',
                'Algebra I / Algebra II'
            )

        union all

        -- hs science courses
        select *, 'COUR-14' as crdc_question_section,
        from custom_schedule
        where crdc_subject_group in ('Biology', 'Chemistry', 'Physics')

        union all

        -- hs computer science courses
        select *, 'COUR-18' as crdc_question_section,
        from custom_schedule
        where crdc_subject_group = 'Computer Science'

        union all

        -- hs data science courses
        select *, 'COUR-20' as crdc_question_section,
        from custom_schedule
        where crdc_subject_group = 'Data Science'

        union all

        -- ap courses that have correct tags on PS
        select *, 'APIB-4' as crdc_question_section,
        from custom_schedule
        -- crdc ap group is needed to not count the AP courses crdc doesnt like
        where ap_tag_mismatch and crdc_ap_group is not null

        union all

        -- ap courses that have incorrect tags on PS
        select *, 'APIB-4' as crdc_question_section,
        from custom_schedule
        -- crdc ap group is needed to not count the AP courses crdc doesnt like
        where not ap_tag_mismatch and is_ap_course and crdc_ap_group is not null
    )

select *
from enrollment
