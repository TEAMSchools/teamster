-- grain projection: every selected column is functionally determined by
-- (course_number, region); not a dedupe mask
select distinct
    concat(cs._dbt_source_project, '-', cs.sections_course_number) as course_id,
    {{ branchingminds_district_id(extract_region("cs")) }} as district_id,
    cs.courses_course_name as `name`,
    cs.courses_sched_fullcatalogdescription as description,
from {{ ref("int_students__course_sections") }} as cs
where
    cs._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
    and cs.terms_academic_year = {{ var("current_academic_year") }}
    and cs.sections_no_of_students > 0
