with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("deanslist", "src_deanslist__homework"),
                partition_by="DLSAID",
                order_by="_file_name desc",
            )
        }}
    )

select
    cast(nullif(dlsaid, '') as int) as dl_said,
    cast(nullif(behaviorid, '') as int) as behavior_id,
    cast(nullif(dlorganizationid, '') as int) as dl_organization_id,
    cast(nullif(dlschoolid, '') as int) as dl_school_id,
    cast(nullif(dlstudentid, '') as int) as dl_student_id,
    cast(nullif(dluserid, '') as int) as dl_user_id,
    cast(nullif(pointvalue, '') as int) as point_value,
    cast(nullif(rosterid, '') as int) as roster_id,
    cast(nullif(secondarystudentid, '') as int) as secondary_student_id,
    cast(nullif(staffschoolid, '') as int) as staff_school_id,
    cast(nullif(studentschoolid, '') as int) as student_school_id,
    cast(nullif(behaviordate, '') as date) as behavior_date,
    cast(nullif(dl_lastupdate, '') as datetime) as dl_last_update,

    nullif(assignment, '') as `assignment`,
    nullif(behavior, '') as behavior,
    nullif(behaviorcategory, '') as behavior_category,
    nullif(notes, '') as notes,
    nullif(roster, '') as roster,
    nullif(schoolname, '') as school_name,
    nullif(stafftitle, '') as staff_title,
    nullif(stafffirstname, '') as staff_first_name,
    nullif(staffmiddlename, '') as staff_middle_name,
    nullif(stafflastname, '') as staff_last_name,
    nullif(studentfirstname, '') as student_first_name,
    nullif(studentmiddlename, '') as student_middle_name,
    nullif(studentlastname, '') as student_last_name,
    nullif(`weight`, '') as `weight`,
from deduplicate
where not is_deleted or is_deleted is null
