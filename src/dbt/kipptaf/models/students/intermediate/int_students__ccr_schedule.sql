with
    /* Every course enrollment that can stand in for a student's College and
       Career Readiness (CCR) schedule, tagged with which tier it belongs to.
       courses_credittype cannot identify a CCR course -- SEM022151G4 is STUDY in
       Camden and CAREER in Newark -- and courses_sched_coursesubjectareacode is
       null on every row, so the course name carries the match. discipline is a
       second net for a CCR course whose name stops following the pattern. */
    schedule_candidates as (
        select
            students_student_number as student_number,
            cc_academic_year as academic_year,
            cc_termid,
            cc_dateenrolled,
            cc_dateleft,
            cc_sectionid,
            courses_course_name,
            teacher_lastfirst,

            /* sections_external_expression reads HR(A) or HR(R) on every
               homeroom section and carries no period, so homeroom reports its
               section number (9M311) instead. */
            if(
                courses_credittype = 'HR',
                sections_section_number,
                sections_external_expression
            ) as schedule_section,

            case
                when
                    courses_course_name like 'College and Career%' or discipline = 'CCR'
                then 'CCR'
                when cc_course_number = 'SEM22106G1'
                then 'Advisory'
                when courses_credittype = 'HR'
                then 'Homeroom'
            end as schedule_source,

        from {{ ref("base_powerschool__course_enrollments") }}
        where not is_dropped_section
    ),

    /* An active CCR course first, then KIPP Newark Lab's Advisory course, then
       homeroom. Homeroom is the universal backstop -- from SY26-27 the regions
       schedule CCR for grades 11 and 12 only, so a grade 9 or 10 student would
       otherwise have no schedule to report at all.

       Partition on student_number, which is canonical across districts. Do NOT
       reach for cc_studyear here: it is district-scoped and collides across
       Camden and Newark in this union.

       cc_sectionid ends the order because 12 SY26-27 students sit in two
       non-dropped homerooms with identical termid, dateenrolled and dateleft.
       Nothing distinguishes those rows, so the pick is arbitrary -- but it has
       to be STABLE, or the teacher and section flap between refreshes. */
    ranked as (
        select
            student_number,
            academic_year,
            courses_course_name,
            teacher_lastfirst,
            schedule_section,
            schedule_source,

            row_number() over (
                partition by student_number, academic_year
                order by
                    case
                        schedule_source when 'CCR' then 1 when 'Advisory' then 2 else 3
                    end,
                    cc_termid desc,
                    cc_dateenrolled desc,
                    cc_dateleft desc,
                    cc_sectionid asc
            ) as rn_schedule,

        from schedule_candidates
        where schedule_source is not null
    )

select
    student_number,
    academic_year,
    courses_course_name as ccr_course,
    teacher_lastfirst as ccr_teacher_name,
    schedule_section as ccr_section,
    schedule_source as ccr_course_source,

from ranked
where rn_schedule = 1
