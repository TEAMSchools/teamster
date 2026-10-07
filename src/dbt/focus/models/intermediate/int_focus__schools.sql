select
    -- school_level is replaced below with the network-vocabulary value; the
    -- staging column it shadows is the raw Focus select-option id, which only
    -- the pivot needs.
    s.* except (school_level),

    p.school_level_label,
    p.school_type_label,
    p.technical_center_label,

    case
        p.school_level_label
        when 'E - Elementary'
        then 'ES'
        when 'M - Middle'
        then 'MS'
        when 'H - High'
        then 'HS'
    end as school_level,
from {{ ref("stg_focus__schools") }} as s
left join {{ ref("int_focus__schools__pivot") }} as p on s.id = p.id
