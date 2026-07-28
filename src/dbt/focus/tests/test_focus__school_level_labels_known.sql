-- Guards the school_level decode in int_focus__student_enrollment, which maps
-- these SISSchool level labels to the ES/MS/HS abbreviation. A Focus label
-- rename, or a new level Focus starts assigning, would otherwise null
-- school_level silently. Any returned row is a failure.
select id, school_level_label,
from {{ ref("int_focus__schools__pivot") }}
where
    school_level_label is not null
    and school_level_label
    not in ('E - Elementary', 'M - Middle', 'H - High', 'C - Combined')
