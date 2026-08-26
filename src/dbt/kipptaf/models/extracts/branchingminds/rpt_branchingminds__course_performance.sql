with
    -- grain projection: student_number is functionally determined by
    -- studentid within a region, so DISTINCT here is a projection, not a
    -- dedupe mask
    enrollments as (
        select distinct studentid, student_number, _dbt_source_project,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        where academic_year = {{ var("current_academic_year") }}
    )

select
    cast({{ var("current_academic_year") }} + 1 as string) as school_year_id,

    concat(sg._dbt_source_project, '-', cast(sg.dcid as string)) as record_id,
    cast(enr.student_number as string) as student_id,
    concat(sg._dbt_source_project, '-', sg.course_number) as course_id,
    cast(sg.percent as string) as `grade`,
from {{ ref("stg_powerschool__storedgrades") }} as sg
inner join
    enrollments as enr
    on sg.studentid = enr.studentid
    and sg._dbt_source_project = enr._dbt_source_project
where
    sg._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
    and sg.termid >= 3600
    and sg.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
