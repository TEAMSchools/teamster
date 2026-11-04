-- Guards the join-key repoint in int_assessments__course_enrollments and
-- int_extracts__course_enrollments_by_term. Both once joined on PowerSchool's
-- internal cc_studentid / studentid, which Focus leaves null, so both silently
-- held zero Miami rows in every year -- a failure with no error anywhere. A
-- revert to those keys would re-drop Miami just as quietly, so assert the rows
-- are present rather than trusting the join to stay correct.
--
-- Deliberately a presence check, not a count floor: Miami's row count moves
-- with enrollment, and a floor would either drift stale or fire on real
-- change. Zero rows is the only value that is always wrong.
with
    miami_rows as (
        select
            'int_assessments__course_enrollments' as model_name,
            countif(_dbt_source_project = 'kippmiami') as miami_row_count,
        from {{ ref("int_assessments__course_enrollments") }}

        union all

        select
            'int_extracts__course_enrollments_by_term' as model_name,
            countif(_dbt_source_project = 'kippmiami') as miami_row_count,
        from {{ ref("int_extracts__course_enrollments_by_term") }}
    )

select model_name, miami_row_count,
from miami_rows
where miami_row_count = 0
