-- grain projection: every selected column is functionally determined by
-- (course_number, region); not a dedupe mask
-- trunk-ignore(sqlfluff/ST06): column order fixed by the Branching Minds template
select distinct
    concat(cs._dbt_source_project, '-', cs.sections_course_number) as course_id,
    dr.branchingminds_district_id as district_id,
    cs.courses_course_name as `name`,
    cs.courses_sched_fullcatalogdescription as description,
from {{ ref("int_students__course_sections") }} as cs
inner join
    {{ ref("dim_regions") }} as dr on cs._dbt_source_project = dr.dagster_code_location
where
    dr.branchingminds_district_id is not null
    and cs.terms_academic_year = {{ var("current_academic_year") }}
    and cs.sections_no_of_students > 0
