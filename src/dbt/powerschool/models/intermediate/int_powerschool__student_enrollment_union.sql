with
    stu_reenr as (
        /* pre-enrolled, current, transferred out */
        select
            id as studentid,
            dcid as students_dcid,
            student_number,
            grade_level,
            schoolid,
            entrydate,
            exitdate,
            entrycode,
            exitcode,
            exitcomment,
            lunchstatus,
            fteid,
            state_studentnumber,
            first_name,
            middle_name,
            last_name,
            lastfirst,
            enroll_status,
            dob,
            street,
            city,
            `state`,
            zip,
            home_phone,
            fedethnicity,
            next_school,
            sched_nextyeargrade,
            grade_level as highest_grade_level_achieved,
            gender_code as gender,
            ethnicity_code as ethnicity,
            track,

            null as reenrollments_dcid,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status in (-1, 0, 2) and exitdate > entrydate

        union all

        /* re-enrollments */
        select
            re.studentid,

            s.dcid as students_dcid,
            s.student_number,

            re.grade_level,
            re.schoolid,
            re.entrydate,
            re.exitdate,
            re.entrycode,
            re.exitcode,
            re.exitcomment,
            re.lunchstatus,
            re.fteid,

            s.state_studentnumber,
            s.first_name,
            s.middle_name,
            s.last_name,
            s.lastfirst,
            s.enroll_status,
            s.dob,
            s.street,
            s.city,
            s.state,
            s.zip,
            s.home_phone,
            s.fedethnicity,

            null as next_school,
            null as sched_nextyeargrade,

            s.grade_level as highest_grade_level_achieved,
            s.gender_code as gender,
            s.ethnicity_code as ethnicity,

            re.track,
            re.dcid as reenrollments_dcid,
        from {{ ref("stg_powerschool__reenrollments") }} as re
        inner join {{ ref("stg_powerschool__students") }} as s on re.studentid = s.id
        where
            re.schoolid != 12345  -- filter out summer school
            and re.exitdate > re.entrydate
    ),

    with_terms_ext as (
        select sr.*, terms.yearid, terms.academic_year,
        from stu_reenr as sr
        inner join
            {{ ref("stg_powerschool__terms") }} as terms
            on sr.schoolid = terms.schoolid
            and sr.entrydate between terms.firstday and terms.lastday
            and terms.isyearrec = 1
    )

select
    studentid,
    students_dcid,
    student_number,
    reenrollments_dcid,
    grade_level,
    schoolid,
    entrydate,
    exitdate,
    entrycode,
    exitcode,
    exitcomment,
    lunchstatus,
    fteid,
    state_studentnumber,
    first_name,
    middle_name,
    last_name,
    lastfirst,
    enroll_status,
    dob,
    street,
    city,
    `state`,
    zip,
    home_phone,
    fedethnicity,
    next_school,
    sched_nextyeargrade,
    highest_grade_level_achieved,
    gender,
    ethnicity,
    yearid,
    academic_year,

    coalesce(track, 'A') as track,
from with_terms_ext

union all

/* graduates */
select
    s.id as studentid,
    s.dcid as students_dcid,
    s.student_number,

    null as reenrollments_dcid,

    s.grade_level,
    s.schoolid,

    null as entrydate,
    null as exitdate,
    null as entrycode,
    null as exitcode,
    null as exitcomment,
    null as lunchstatus,
    null as fteid,

    s.state_studentnumber,
    s.first_name,
    s.middle_name,
    s.last_name,
    s.lastfirst,
    s.enroll_status,
    s.dob,
    s.street,
    s.city,
    s.state,
    s.zip,
    s.home_phone,
    s.fedethnicity,

    null as next_school,
    null as sched_nextyeargrade,

    s.grade_level as highest_grade_level_achieved,
    s.gender_code as gender,
    s.ethnicity_code as ethnicity,

    terms.yearid,
    terms.academic_year,

    null as track,
from {{ ref("stg_powerschool__students") }} as s
inner join
    {{ ref("stg_powerschool__terms") }} as terms
    on s.schoolid = terms.schoolid
    and s.entrydate <= terms.firstday
    and terms.isyearrec = 1
where s.enroll_status = 3
