-- Compatibility passthrough. The enrollment logic moved to
-- int_students__student_enrollments, which carries both SIS branches; this
-- model exists so the consumers listed in #3999 keep resolving while they
-- migrate. Delete it once they have. As a select * view it keeps the column
-- list it was created with: edit this file when the upstream gains a column,
-- or Dagster never rebuilds it.
select *, from {{ ref("int_students__student_enrollments") }}
