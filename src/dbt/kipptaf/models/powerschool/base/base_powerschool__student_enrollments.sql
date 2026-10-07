-- Compatibility passthrough. The enrollment logic moved to
-- int_students__student_enrollments, which carries both SIS branches; this
-- model exists so the consumers listed in #3999 keep resolving while they
-- migrate. Delete it once they have.
select *, from {{ ref("int_students__student_enrollments") }}
