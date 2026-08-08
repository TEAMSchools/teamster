select
    s._dbt_source_relation,
    s._dbt_source_project,
    s.title as `name`,

    loc.location_key,
    loc.abbreviation,
    loc.powerschool_school_id as school_number,

    -- Focus's ZZ Course History and Virtual Franchise administrative entries
    -- have no location match and are excluded by the inner join below, so
    -- school_level is always populated for a real school here. The two closed
    -- schools (Liberty, Sunrise) carry no school_level_label in Focus, matching
    -- the archive's own null for closed/inactive schools.
    case
        s.school_level_label
        when 'E - Elementary'
        then 'ES'
        when 'M - Middle'
        then 'MS'
        when 'H - High'
        then 'HS'
    end as school_level,
from {{ ref("int_focus__schools") }} as s
inner join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on s.school_number = loc.focus_school_id
