with
    -- Miami school identity from Focus, conformed to the PowerSchool school
    -- spine's vocabulary and keyed on the PowerSchool numeric school id instead
    -- of Focus's own school code, so it merges into the network school spine
    -- below by column name. Limited to schools with a match on the people
    -- locations sheet; Focus's non-physical administrative entries (ZZ Course
    -- History, Virtual Franchise) have no such match and are excluded.
    focus_conformed as (
        select
            s._dbt_source_relation,
            s._dbt_source_project,
            s.title as `name`,

            loc.location_key,
            loc.abbreviation,
            loc.powerschool_school_id as school_number,

            -- Decoded in int_focus__schools. Focus's ZZ Course History and
            -- Virtual Franchise administrative entries have no location match
            -- and are excluded by the inner join below, so this is populated
            -- for every real school here. The two closed schools (Liberty,
            -- Sunrise) carry no level in Focus, matching the archive's own
            -- null for closed/inactive schools.
            s.school_level,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    -- Focus is Miami's system of record for schools, so the frozen archive
    -- contributes no rows. That drops the archive's 999999 "Graduated
    -- Students" sentinel along with it, which is fine now that the Miami
    -- alumni graduate placeholder enrollments it served are gone too.
    powerschool_filtered as (
        select p.*,
        from {{ ref("stg_powerschool__schools") }} as p
        where p._dbt_source_project != 'kippmiami'
    )

select *,
from powerschool_filtered

full union all corresponding

select *,
from focus_conformed
