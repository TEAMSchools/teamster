-- trunk-ignore(sqlfluff/ST06): column order fixed by the Branching Minds template
select
    concat(sg._dbt_source_project, '-', cast(sg.dcid as string)) as record_id,
    cast(s.student_number as string) as student_id,
    concat(sg._dbt_source_project, '-', sg.course_number) as course_id,
    cast(sg.academic_year + 1 as string) as school_year_id,
    cast(sg.percent as string) as `grade`,
from {{ ref("stg_powerschool__storedgrades") }} as sg
inner join
    {{ ref("stg_powerschool__students") }} as s
    on sg.studentid = s.id
    and sg._dbt_source_project = s._dbt_source_project
where
    sg._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
    and sg.academic_year = {{ var("current_academic_year") }}
    and sg.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
    -- grade is required by the vendor; a stored grade with no percent is unusable
    and sg.percent is not null
