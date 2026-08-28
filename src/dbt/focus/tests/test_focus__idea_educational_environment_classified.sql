-- Guards the custom_863 decode that drives is_out_of_district and its three
-- companion columns in int_students__student_enrollments (#5041). Every option
-- must be one the derivation classifies: C, D, F, H and P are out-of-district
-- placements, Z and N/A are no placement. Anything else is one of Florida's
-- age 3-5 options, excluded because Miami enrolls no pre-K -- if one appears,
-- the student reports as in-district on an unexamined assumption. A null code
-- beside a populated raw value fails too, which is a broken decode join rather
-- than a new option. Any returned row is a warning.
select student_id, idea_educational_environment, idea_educational_environment_code,
from {{ ref("int_focus__students") }}
where
    idea_educational_environment is not null
    and coalesce(idea_educational_environment_code, '?')
    not in ('Z', 'N/A', 'C', 'D', 'F', 'H', 'P')
