-- Staging columns plus their decoded custom-field labels. Drives from staging
-- and LEFT JOINs the pivot: BigQuery UNPIVOT drops entities whose unpivoted
-- columns are all null, so the pivot alone is not a complete entity spine.
select
    -- school_level is replaced below with the network-vocabulary value; the
    -- staging column it shadows is the raw Focus select-option id, which only
    -- the pivot needs.
    s.* except (school_level),

    p.school_level_label,
    p.school_type_label,
    p.technical_center_label,

    -- Network-vocabulary school level. Null for Combined and Adult/Higher-Ed
    -- schools, and for closed legacy schools that carry no school_level_label.
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
