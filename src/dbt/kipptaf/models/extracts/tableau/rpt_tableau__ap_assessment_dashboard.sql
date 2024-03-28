with
    ap_assessments_official as (
        select
            contact,
            date as test_date,
            score as scale_score,
            rn_highest,

            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,

            case
                test_subject
                when 'Physics 1: Algebra-Based'
                then 'AP Physics 1'
                when 'Studio Art: 2-D Design Portfolio'
                then 'AP Studio Art: Two-Dimensional'
                when 'United States Government and Politics'
                then 'AP US Government and Politics'
                when 'United States History'
                then 'AP US History'
                else concat('AP ', test_subject)
            end as test_subject_area,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where score_type = 'ap'
    )

select
    e.student_number,
    e.lastfirst,
    e.enroll_status,
    e.cohort,
    e.academic_year,
    e.region,
    e.schoolid,
    e.school_abbreviation,
    e.grade_level,
    e.advisor_lastfirst,
    e.is_enrolled_recent,
    e.is_enrolled_y1,
    e.entrydate,
    e.exitdate,
    e.is_504 as c_504_status,
    e.lep_status,

    s.cc_dateenrolled as ap_date_enrolled,
    s.cc_dateleft as ap_date_left,
    s.sections_external_expression as ap_course_section,
    s.teacher_lastfirst as ap_teacher_name,

    x.ap_course_subject,

    adb.id as contact_id,
    adb.kipp_hs_class as ktc_cohort,

    a.administration_round,
    a.test_date,
    a.scale_score,
    a.rn_highest,

    if(e.spedlep in ('No IEP', null), 0, 1) as sped,

    coalesce(s.courses_course_name, 'Not an AP course') as ap_course_name,
    if(s.courses_course_name is null, 'Not applicable', 'AP') as expected_scope,
    if(
        s.courses_course_name is null, 'Not applicable', 'Official'
    ) as expected_test_type,

    case
        when s.courses_course_name is null
        then 'Not applicable'
        when s.courses_course_name is not null and a.test_subject_area is null
        then 'Took course, but not AP exam.'
        else a.test_subject_area
    end as test_subject_area,
from {{ ref("base_powerschool__student_enrollments") }} as e
left join
    {{ ref("base_powerschool__course_enrollments") }} as s
    on e.studentid = s.cc_studentid
    and e.academic_year = s.cc_academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
    and s.rn_course_number_year = 1
    and s.courses_course_name like 'AP%'
    and not s.is_dropped_section
left join
    {{ ref("stg_powerschool__s_nj_crs_x") }} as x
    on s.courses_dcid = x.coursesdcid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="x") }}
left join
    {{ ref("stg_kippadb__contact") }} as adb
    on e.student_number = adb.school_specific_id
left join
    ap_assessments_official as a
    on adb.id = a.contact
    and s.courses_course_name = a.test_subject_area
where
    e.rn_year = 1
    and e.school_level = 'HS'
    and date(e.academic_year + 1, 05, 15) between e.entrydate and e.exitdate
