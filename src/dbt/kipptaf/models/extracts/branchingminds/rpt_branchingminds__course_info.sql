with
    -- grain projection: every selected column is functionally determined
    -- by (course_number, region); not a dedupe mask
    active_sections as (
        select distinct bs._dbt_source_project, bs.sections_course_number,
        from {{ ref("base_powerschool__sections") }} as bs
        where
            bs._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and bs.sections_termid >= 3600
            and bs.sections_no_of_students > 0
    )

select
    -- course_number is per-district catalog, not globally unique --
    -- district_id below disambiguates instead
    c.course_number as course_id,
    c.course_name as `name`,
    c.sched_fullcatalogdescription as description,

    case
        c._dbt_source_project
        when 'kippnewark'
        then '7325'
        when 'kippcamden'
        then '1799'
        when 'kipppaterson'
        then '7899'
    end as district_id,
from {{ ref("stg_powerschool__courses") }} as c
inner join
    active_sections as asec
    on c.course_number = asec.sections_course_number
    and c._dbt_source_project = asec._dbt_source_project
where c._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
