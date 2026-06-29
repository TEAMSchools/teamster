-- Asserts that int_assessments__resolved_section_enrollments is one row per
-- score. The score grain is the inputs of score_grain_key (not output):
-- (powerschool_student_number, _dbt_source_project, source_type,
-- canonical_assessment_id, academic_year, administration_period, subject_area).
-- NULL-safe via format("%T|...") so NULL canonical_assessment_id on state rows
-- and NULL academic_year/administration_period on internal rows don't collapse
-- distinct counts.
select
    format(
        '%T|%T|%T|%T|%T|%T|%T',
        powerschool_student_number,
        _dbt_source_project,
        source_type,
        canonical_assessment_id,
        academic_year,
        administration_period,
        subject_area
    ) as score_grain,
    count(*) as n,
from {{ ref("int_assessments__resolved_section_enrollments") }}
group by 1
having n > 1
