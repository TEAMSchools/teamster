with
    miami_students as (
        -- grain projection, not dup-masking
        select distinct student_number,
        from {{ ref("int_extracts__student_enrollments") }}
        where region = 'Miami'
    ),

    miami_schools as (
        select school_number,
        from {{ ref("int_students__schools") }}
        where _dbt_source_project = 'kippmiami'
    ),

    miami_staff as (
        -- grain projection, not dup-masking
        select distinct employee_number,
        from {{ ref("int_people__staff_roster") }}
        where home_work_location_dagster_code_location = 'kippmiami'
    ),

    course_regions as (
        select
            course_number,

            logical_or(_dbt_source_project = 'kippmiami') as is_miami,
            logical_or(_dbt_source_project != 'kippmiami') as is_nj,
        from {{ ref("int_students__courses") }}
        group by course_number
    ),

    miami_only_courses as (
        select course_number, from course_regions where is_miami and not is_nj
    )

-- trunk-ignore-begin(sqlfluff/RF05)
select 'studemo' as feed, cast(f.`01 Import Student ID` as string) as feed_key,
from {{ ref("rpt_illuminate__studemo") }} as f
inner join miami_students as m on f.`01 Import Student ID` = m.student_number

union all

select 'enrollment' as feed, cast(f.`01 Student ID` as string) as feed_key,
from {{ ref("rpt_illuminate__enrollment") }} as f
inner join miami_students as m on f.`01 Student ID` = m.student_number

union all

select 'programs' as feed, cast(f.`01 Import Student ID` as string) as feed_key,
from {{ ref("rpt_illuminate__programs") }} as f
inner join miami_students as m on f.`01 Import Student ID` = m.student_number

union all

select 'student_portal_accounts' as feed, cast(f.`01 Student ID` as string) as feed_key,
from {{ ref("rpt_illuminate__student_portal_accounts") }} as f
inner join miami_students as m on f.`01 Student ID` = m.student_number

union all

select 'roster' as feed, cast(f.`01 Student ID` as string) as feed_key,
from {{ ref("rpt_illuminate__roster") }} as f
inner join miami_students as m on f.`01 Student ID` = m.student_number

union all

select 'sites' as feed, cast(f.`01 Site ID` as string) as feed_key,
from {{ ref("rpt_illuminate__sites") }} as f
inner join miami_schools as m on f.`01 Site ID` = m.school_number

union all

select 'terms' as feed, cast(f.`01 Site ID` as string) as feed_key,
from {{ ref("rpt_illuminate__terms") }} as f
inner join miami_schools as m on f.`01 Site ID` = m.school_number

union all

select 'mastschd' as feed, `01 Section ID` as feed_key,
from {{ ref("rpt_illuminate__mastschd") }}
where `01 Section ID` like 'kippmiami%'

union all

select 'courses' as feed, f.`01 Course ID` as feed_key,
from {{ ref("rpt_illuminate__courses") }} as f
inner join miami_only_courses as m on f.`01 Course ID` = m.course_number

union all

select 'users' as feed, cast(f.`10 State User Or Employee ID` as string) as feed_key,
from {{ ref("rpt_illuminate__users") }} as f
inner join miami_staff as m on f.`10 State User Or Employee ID` = m.employee_number

union all

select 'roles' as feed, cast(f.`02 Site ID` as string) as feed_key,
from {{ ref("rpt_illuminate__roles") }} as f
inner join
    miami_schools as m on f.`02 Site ID` = m.school_number
    -- trunk-ignore-end(sqlfluff/RF05)
