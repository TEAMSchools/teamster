with
    finalsite_roster as (
        select
            enrollment_academic_year,
            org,
            region,
            school,
            finalsite_student_id,
            powerschool_student_number,
            last_name,
            first_name,
            grade_level,

        from {{ ref("int_students__finalsite_student_roster") }}
        where
            rn = 1
            and powerschool_student_number is not null
            and latest_status = 'Enrolled'
    )

select
    e.student_number,
    e.student_name,
    e.grade_level,

    if(
        f.powerschool_student_number is null,
        -- trunk-ignore(sqlfluff/LT05)
        'Student is active on PS for the current academic year, but does not have an Enrolled status on FS for current academic year',
        'PS to FS enrollment match'
    ) as enrollment_match,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    finalsite_roster as f
    on e.student_number = f.powerschool_student_number
    and e.academic_year = f.enrollment_academic_year
where e.rn_year = 1 and e.enroll_status = 0

union all

select

    f.powerschool_student_number,
    concat(f.last_name, ', ', f.first_name) as student_name,
    f.grade_level,

    if(
        e.student_number is null,
        -- trunk-ignore(sqlfluff/LT05)
        'Student is tagged as Enrolled on FS for the current academic year, but is not actively enrolled on PS for current academic year',
        'FS to PS enrollment match'
    ) as enrollment_match,

from finalsite_roster as f
left join
    {{ ref("int_extracts__student_enrollments") }} as e
    on f.powerschool_student_number = e.student_number
    and f.enrollment_academic_year = e.academic_year
where e.rn_year = 1 and e.enroll_status = 0
