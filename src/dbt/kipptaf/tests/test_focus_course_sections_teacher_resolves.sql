-- Every Focus section should resolve a lead teacher through the staff roster.
-- All 77 current Miami teachers do, because they predate the Focus migration
-- and still carry a PowerSchool teacher number. A Miami-only hire would not,
-- so this warns rather than errors -- it is an Ops correction in the roster,
-- not a modeling defect.
select sections_dcid, _dbt_source_project,
from {{ ref("int_students__course_sections") }}
where _dbt_source_project = 'kippmiami' and teachernumber is null
