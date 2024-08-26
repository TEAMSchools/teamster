select
    o.observation_id,

    mn.`column` as notes_column,
    mn.shared as notes_shared,
    mn.text as notes_text,
    mn.created as notes_created,
    mn._id as notes_id,

from {{ ref("stg_schoolmint_grow__observations") }} as o
cross join unnest(o.magic_notes) as mn
