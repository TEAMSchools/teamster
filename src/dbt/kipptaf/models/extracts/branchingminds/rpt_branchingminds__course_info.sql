with
    -- courses with at least one enrolled section this year
    active_courses as (
        select _dbt_source_project, sections_course_number,
        from {{ ref("int_students__course_sections") }}
        where terms_academic_year = {{ var("current_academic_year") }}
        group by _dbt_source_project, sections_course_number
        having sum(sections_no_of_students) > 0
    )

select
    c.course_name as `name`,
    c.sched_fullcatalogdescription as description,

    dr.state_district_id as district_id,

    concat(c._dbt_source_project, '-', c.course_number) as course_id,
from {{ ref("stg_powerschool__courses") }} as c
inner join
    active_courses as ac
    on c.course_number = ac.sections_course_number
    and c._dbt_source_project = ac._dbt_source_project
inner join
    {{ ref("dim_regions") }} as dr on c._dbt_source_project = dr.dagster_code_location
where dr.name in ('Newark', 'Camden', 'Paterson')
