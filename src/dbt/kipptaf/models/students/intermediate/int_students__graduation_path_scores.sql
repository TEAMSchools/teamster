-- note for charlie and charlie only. if you are not charlie, look away: the intent of
-- this new int table is to replace several duplicated ctes that are used on the
-- int_students__graduation_path_codes view, and on the
-- rpt_tableau__graduation_requirements view. i anticipate this new int view below
-- also becoming a source for future graduation eligibility projects as we add to the
-- mix with credit tracking efforts for HS students. i would have also made this new
-- source a table, but i still dont understand how to do that, no matter how many
-- examples i see online. if you could turn it into a table (if it makes sesnse), it
-- would be much appreciated. thanks!
with
    students as (
        select
            e._dbt_source_relation,
            e.students_dcid,
            e.studentid,
            e.student_number,
            e.state_studentnumber,
            e.contact_id as kippadb_contact_id,
            e.cohort,
            e.enroll_status,

            max(e.grade_level) as most_recent_grade_level,

            discipline,

        from {{ ref("int_tableau__student_enrollments") }} as e
        cross join unnest(['Math', 'ELA']) as discipline
        where e.grade_level between 9 and 12
        group by all
    )

select *
from students
