with
    /* One row per student holding all three SAT highlights, replacing three
       separate left joins to the same model that differed only by subject area.
       rn_highest = 1 already yields one row per student per subject area, so the
       aggregate picks rather than collapses. */
    sat_highlights as (
        select
            student_number,

            max(
                if(aligned_subject_area = 'Total', superscore, null)
            ) as sat_total_superscore,
            max(
                if(aligned_subject_area = 'EBRW', max_scale_score, null)
            ) as sat_ebrw_highest,
            max(
                if(aligned_subject_area = 'Math', max_scale_score, null)
            ) as sat_math_highest,

        from {{ ref("int_assessments__college_assessment") }}
        where
            scope = 'SAT'
            and rn_highest = 1
            and aligned_subject_area in ('Total', 'EBRW', 'Math')
        group by student_number
    ),

    /* Every course enrollment that can stand in for a student's College and
       Career Readiness (CCR) schedule, tagged with which tier it belongs to.
       courses_credittype cannot identify a CCR course -- SEM022151G4 is STUDY in
       Camden and CAREER in Newark -- and courses_sched_coursesubjectareacode is
       null on every row, so the course name carries the match. The crosswalk is
       a second net for a CCR course whose name stops following the pattern; it
       holds one row per course number, so it cannot fan out. */
    schedule_candidates as (
        select
            c._dbt_source_relation,
            c.students_student_number,
            c.cc_academic_year,
            c.cc_termid,
            c.cc_dateenrolled,
            c.courses_course_name,
            c.teacher_lastfirst,

            /* sections_external_expression reads HR(A) or HR(R) on every
               homeroom section and carries no period, so homeroom reports its
               section number (9M311) instead. */
            if(
                c.courses_credittype = 'HR',
                c.sections_section_number,
                c.sections_external_expression
            ) as schedule_section,

            case
                when
                    c.courses_course_name like 'College and Career%'
                    or csc.discipline = 'CCR'
                then 'CCR'
                when c.cc_course_number = 'SEM22106G1'
                then 'Advisory'
                when c.courses_credittype = 'HR'
                then 'Homeroom'
            end as schedule_source,

        from {{ ref("base_powerschool__course_enrollments") }} as c
        left join
            {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
            on c.cc_course_number = csc.powerschool_course_number
        where not c.is_dropped_section
    ),

    /* One scheduling row per student: an active CCR course first, then KIPP
       Newark Lab's Advisory course, then homeroom. Homeroom is the universal
       backstop -- from SY26-27 the regions schedule CCR for grades 11 and 12
       only, so a grade 9 or 10 student would otherwise read No Data.

       Partition on _dbt_source_relation as well as the student. cc_studyear is
       district-scoped and collides across Camden and Newark in this union, so
       partitioning on it drops one student from each colliding pair. */
    student_schedule as (
        select
            students_student_number,
            cc_academic_year,
            courses_course_name,
            teacher_lastfirst,
            schedule_section,
            schedule_source,

            row_number() over (
                partition by
                    _dbt_source_relation, students_student_number, cc_academic_year
                order by
                    case
                        schedule_source when 'CCR' then 1 when 'Advisory' then 2 else 3
                    end,
                    cc_termid desc,
                    cc_dateenrolled desc
            ) as rn_schedule,

        from schedule_candidates
        where schedule_source is not null
    )

select
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.salesforce_id,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.student_email,
    e.enroll_status,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.iep_status,
    e.grad_iep_exempt_status_overall,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_projected,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    ea.expected_test_type,
    ea.expected_scope,
    ea.expected_score_type,
    ea.expected_grouping,
    ea.expected_grade_level,
    ea.expected_admin_season,
    ea.expected_months_included,
    ea.expected_field_name,
    ea.expected_score_category,
    ea.expected_admin_season_order,

    a.score,

    sh.sat_total_superscore,
    sh.sat_ebrw_highest,
    sh.sat_math_highest,

    concat(
        ea.expected_field_name, ' ', ea.expected_score_category
    ) as expected_field_name_score_category,

    coalesce(p.psat89_count_lifetime, 0) as psat89_count_lifetime,
    coalesce(p.psat10_count_lifetime, 0) as psat10_count_lifetime,
    coalesce(p.psatnmsqt_count_lifetime, 0) as psatnmsqt_count_lifetime,
    coalesce(p.sat_count_lifetime, 0) as sat_count_lifetime,
    coalesce(p.act_count_lifetime, 0) as act_count_lifetime,

    coalesce(sch.courses_course_name, 'No Data') as ccr_course,
    coalesce(sch.teacher_lastfirst, 'No Data') as ccr_teacher_name,
    coalesce(sch.schedule_section, 'No Data') as ccr_section,
    coalesce(sch.schedule_source, 'No Data') as ccr_course_source,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("stg_google_sheets__kippfwd__expected_assessments") }} as ea
    on e.region = ea.expected_region
    and ea.rn = 1
left join
    {{ ref("int_tableau__college_assessment_roster_scores") }} as a
    on e.student_number = a.student_number
    and ea.expected_unique_test_admin_id = a.unique_test_admin_id
    and ea.expected_score_category = a.score_category
left join sat_highlights as sh on e.student_number = sh.student_number
left join
    student_schedule as sch
    on e.student_number = sch.students_student_number
    and e.academic_year = sch.cc_academic_year
    and sch.rn_schedule = 1
left join
    {{ ref("int_students__college_assessment_participation_roster") }} as p
    on e.student_number = p.student_number
    and p.test_type = 'Official'
    and p.rn_lifetime = 1
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.graduation_year >= {{ var("current_academic_year") + 1 }}
    and e.school_level = 'HS'
    and e.rn_year = 1
    and not e.is_out_of_district
