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

            -- Focus's ZZ Course History and Virtual Franchise administrative
            -- entries have no location match and are excluded by the inner join
            -- below, so school_level is always populated for a real school
            -- here. The two closed schools (Liberty, Sunrise) carry no
            -- school_level_label in Focus, matching the archive's own null for
            -- closed/inactive schools.
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
    ),

    focus_schools as (select school_number, from focus_conformed),

    -- Focus supersedes the frozen archive for every Miami school it carries, so
    -- an archive row for such a school would double-count. The archive still
    -- holds the 999999 "Graduated Students" sentinel Focus never received,
    -- which the 1,002 alumni graduate placeholder enrollment rows (Task 8)
    -- join to directly -- dropping it would null-fill their school attributes
    -- in dim_student_enrollments.
    powerschool_filtered as (
        select p.*,
        from {{ ref("stg_powerschool__schools") }} as p
        left join focus_schools as f on p.school_number = f.school_number
        where p._dbt_source_project != 'kippmiami' or f.school_number is null
    )

select *,
from powerschool_filtered

full union all corresponding

select *,
from focus_conformed
