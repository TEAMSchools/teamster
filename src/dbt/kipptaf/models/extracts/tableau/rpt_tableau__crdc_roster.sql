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

    -- because of the manual check cte, this cte will have dups, but they will be
    -- addressed in the main select statement when the question group counts are
    -- calculated
    enrollment as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.region,
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

            -- need this to join to act/sat scores
            adb.contact_id,

            -- tag the manual entry for student numbers on the crdc student crosswalk
            -- g-sheet feed
            me.crdc_question_section,
            coalesce(r.is_retained_year, false) as is_retained_year,

            case
                e.gender
                when 'F'
                then 'Female'
                when 'M'
                then 'Male'
                when 'X'
                then 'Nonbinary'
            end as crdc_gender,

            case
                e.ethnicity
                when 'H'
                then 'Hispanic or Latino of any race'
                when 'I'
                then 'American Indian or Alaska Native'
                when 'A'
                then 'Asian'
                when 'P'
                then 'Native Hawaiian or Other Pacific Islander'
                when 'B'
                then 'Black or African American'
                when 'W'
                then 'White'
                when 'T'
                then 'Two or more races'
            end as crdc_demographic,

            -- bring over the manual entry student numbers that match the crdc
            -- question tag
            if(me.student_number is null, false, true) as crdc_question_section_status,

            if(
                e.exitdate = date(e.academic_year + 1, 06, 30), true, false
            ) as is_last_day_enrolled,

            if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

            if(e.spedlep like 'SPED%' and not is_504, true, false) as iep_only,

            if(e.spedlep like 'SPED%' and is_504, true, false) as iep_and_c504,

            if(e.spedlep not like 'SPED%' and is_504, true, false) as c504_only,

        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        left join retained as r on e.student_number = r.student_number
        left join
            {{ ref("stg_crdc__student_numbers") }} as me
            on e.student_number = me.student_number
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
                -- any other school would be a credit recovery course taken
                -- outside of KTAF
                and g.schoolname = 'KIPP Summer School',
                true,
                false
            ) as is_credit_recovery,

            -- some data is needed as of fall snapshot
            if(
                c.cc_dateenrolled <= '2023-10-02' and c.cc_dateleft >= '2023-10-02',
                true,
                false
            ) as is_oct_01_course,

            -- some data is needed as of the last day of school
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

    -- this CTE is appending the different versions/groupings i need for reporting
    -- courses
    final_schedule as (
        -- data dual enrolled students
        select *, 'PENR-4' as crdc_question_section,
        from custom_schedule
        where is_dual_enrollment and is_oct_01_course and not ap_tag

        union all

        -- credit recovery students
        select *, 'PENR-6' as crdc_question_section,
        from custom_schedule
        where is_credit_recovery

        union all

        -- algebra classes for MS; we don't do geometry, so there will be no cte
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
        select
            *,
            case
                crdc_subject_group
                when 'Computer Science'
                then 'COUR-18'
                when 'Data Science'
                then 'COUR-20'
                else 'COUR-14'
            end as crdc_question_section,

        from custom_schedule
        where
            crdc_subject_group
            in ('Biology', 'Chemistry', 'Physics', 'Computer Science', 'Data Science')
            and is_oct_01_course

        union all

        -- ap courses that have correct tags on PS
        select *, 'APIB-4' as crdc_question_section,
        from custom_schedule
        -- crdc ap group is needed to not count the AP courses crdc doesnt like
        where ap_tag_mismatch and crdc_ap_group is not null and is_oct_01_course

        union all

        -- ap courses that have incorrect tags on PS
        select *, 'APIB-4' as crdc_question_section,
        from custom_schedule
        -- crdc ap group is needed to not count the AP courses crdc doesnt like
        where
            not ap_tag_mismatch
            and is_ap_course
            and crdc_ap_group is not null
            and is_oct_01_course
    ),

    act_sat as (
        -- this count(*) serves no purpose other than avoiding a distinct lol
        select contact, count(*) as attempts
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            score_type in ('act_composite', 'sat_total_score')
            and `date` between '2023-08-15' and '2024-06-13'
        group by all
    ),

    -- tracks discipline, ISS/OSS and restraints
    discipline_rollup as (
        select
            dli.student_school_id as student_number,
            dli.create_ts_academic_year as academic_year,

            case
                when
                    count(
                        distinct case
                            when cf.restraint_used = 'Y' then dli.incident_id else null
                        end
                    )
                    > 0
                then 1
                else 0
            end as is_restraint_int,

            count(
                distinct case
                    when cf.restraint_used = 'Y' then dli.incident_id else null
                end
            ) as n_restraint_incidents,

            case
                when
                    count(
                        distinct case
                            when dlp.penalty_name like '%Out-of-School Suspension'
                            then dlp.incident_penalty_id
                        end
                    )
                    = 1
                then 1
                else 0
            end as is_oss_one_int,

            case
                when
                    count(
                        distinct case
                            when dlp.penalty_name like '%Out-of-School Suspension'
                            then dlp.incident_penalty_id
                        end
                    )
                    > 1
                then 1
                else 0
            end as is_oss_two_plus_int,

            max(
                case
                    when dlp.penalty_name like '%In-School Suspension' then 1 else 0
                end
            ) as is_iss_int,

            sum(
                case
                    when dlp.penalty_name like '%Out-of-School Suspension'
                    then dlp.num_days
                    else null
                end
            ) as oss_days_missed,

            count(
                distinct case
                    when dlp.penalty_name like '%Out-of-School Suspension'
                    then dlp.incident_penalty_id
                end
            ) as oss_incident_count,

        from {{ ref("stg_deanslist__incidents") }} as dli
        left join
            {{ ref("stg_deanslist__incidents__penalties") }} as dlp
            on dli.incident_id = dlp.incident_id
            and {{ union_dataset_join_clause(left_alias="dli", right_alias="dlp") }}
        left join
            {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cf
            on dli.incident_id = cf.incident_id
            and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
        where dli.is_active
        group by dli.student_school_id, dli.create_ts_academic_year
    )

-- DSED-2 dups may be present because of students changing schools or grade level
-- midyear
select
    _dbt_source_relation,
    academic_year,
    region,
    schoolid,
    school_abbreviation,

    studentid,
    student_number,
    contact_id,
    grade_level,
    gender,
    ethnicity,
    gifted_and_talented,
    iep_status,
    is_504,
    iep_only,
    iep_and_c504,
    c504_only,
    lep_status,

    entrydate,
    exitdate,
    enroll_status,
    is_enrolled_oct01,
    is_last_day_enrolled,
    is_retained_year,
    rn_year,

    crdc_demographic,
    crdc_gender,

    null as courses_course_name,
    null as sced_course_name,
    null as crdc_course_group,
    null as crdc_subject_group,
    null as crdc_ap_group,
    null as sced_code_xwalk,

    crdc_question_section,
    'Distance Education Enrollment' as crdc_question_description,

from enrollment
where crdc_question_section = 'DSED-2'

union all

-- ENRL-1, 2a,2b, 3, and 4 dups may be present because of
-- students changing schools or grade level midyear
select
    _dbt_source_relation,
    academic_year,
    region,
    schoolid,
    school_abbreviation,

    studentid,
    student_number,
    contact_id,
    grade_level,
    gender,
    ethnicity,
    gifted_and_talented,
    iep_status,
    is_504,
    iep_only,
    iep_and_c504,
    c504_only,
    lep_status,

    entrydate,
    exitdate,
    enroll_status,
    is_enrolled_oct01,
    is_last_day_enrolled,
    is_retained_year,
    rn_year,

    crdc_demographic,
    crdc_gender,

    null as courses_course_name,
    null as sced_course_name,
    null as crdc_course_group,
    null as crdc_subject_group,
    null as crdc_ap_group,
    null as sced_code_xwalk,

    'ENRL' as crdc_question_section,
    'Student Enrollment' as crdc_question_description,

from enrollment
where is_enrolled_oct01

union all
-- PENR-4: there might be dups here if students are taking more than 1 distance
-- learning course
select
    e._dbt_source_relation,
    e.academic_year,
    e.region,
    e.schoolid,
    e.school_abbreviation,

    e.studentid,
    e.student_number,
    e.contact_id,
    e.grade_level,
    e.gender,
    e.ethnicity,
    e.gifted_and_talented,
    e.iep_status,
    e.is_504,
    e.iep_only,
    e.iep_and_c504,
    e.c504_only,
    e.lep_status,

    e.entrydate,
    e.exitdate,
    e.enroll_status,
    e.is_enrolled_oct01,
    e.is_last_day_enrolled,
    e.is_retained_year,
    e.rn_year,

    e.crdc_demographic,
    e.crdc_gender,

    f.courses_course_name,
    f.sced_course_name,
    f.crdc_course_group,
    f.crdc_subject_group,
    f.crdc_ap_group,
    f.sced_code_xwalk,

    f.crdc_question_section,
    'Dual Enrollment' as crdc_question_description,

from enrollment as e
inner join
    final_schedule as f
    on e.schoolid = f.cc_schoolid
    and e.student_number = f.students_student_number
    and e.crdc_question_section = f.crdc_question_section
where
    -- timeframe is fall snapshot
    e.is_enrolled_oct01
    and e.grade_level >= 9
    and e.crdc_question_section = 'PENR-4'
    and f.courses_course_name is not null

union all
-- PENR-6 - there might be dups here if students took more than one credit recovery
-- course
select
    e._dbt_source_relation,
    e.academic_year,
    e.region,
    e.schoolid,
    e.school_abbreviation,

    e.studentid,
    e.student_number,
    e.contact_id,
    e.grade_level,
    e.gender,
    e.ethnicity,
    e.gifted_and_talented,
    e.iep_status,
    e.is_504,
    e.iep_only,
    e.iep_and_c504,
    e.c504_only,
    e.lep_status,

    e.entrydate,
    e.exitdate,
    e.enroll_status,
    e.is_enrolled_oct01,
    e.is_last_day_enrolled,
    e.is_retained_year,
    e.rn_year,

    e.crdc_demographic,
    e.crdc_gender,

    f.courses_course_name,
    f.sced_course_name,
    f.crdc_course_group,
    f.crdc_subject_group,
    f.crdc_ap_group,
    f.sced_code_xwalk,

    f.crdc_question_section,
    'Credit Recovery' as crdc_question_description,

from enrollment as e
inner join
    final_schedule as f
    on e.schoolid = f.cc_schoolid
    and e.student_number = f.students_student_number
    and e.crdc_question_section = f.crdc_question_section
where
    -- timeframe is any part of the year + summer
    e.grade_level >= 9
    and e.crdc_question_section = 'PENR-6'
    and f.courses_course_name is not nulll
