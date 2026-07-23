{% set scaffold_source_mode = var("finalsite_scaffold_source", "blend") %}
{% if scaffold_source_mode not in ("gsheet", "powerschool", "blend") %}
    {{
        exceptions.raise_compiler_error(
            "finalsite_scaffold_source must be 'gsheet', 'powerschool', or"
            ~ " 'blend' -- got '"
            ~ scaffold_source_mode
            ~ "'"
        )
    }}
{% endif %}

with
    powerschool_region as (
        select
            sps.school_number, sps.abbreviation, {{ extract_region("sps") }} as region,

        from {{ ref("stg_powerschool__schools") }} as sps
        where sps.state_excludefromreporting = 0
    ),

    -- Miami's SIS moved to Focus (#4441); stg_powerschool__schools' Miami
    -- rows are a frozen pre-migration snapshot, not a live source of truth.
    -- Deliberate, temporary carve-out -- confirmed with the team to keep
    -- Miami 100% sheet-sourced regardless of finalsite_scaffold_source
    -- until Focus is ready as a scaffold source. Remove this filter (and
    -- update the sheet-side builder's Miami note below) once that happens.
    powerschool_schools as (
        select school_number, abbreviation, region,
        from powerschool_region
        where region != 'Miami'
    ),

    -- Grade membership comes from actual current enrollment, not
    -- stg_powerschool__schools.low_grade/high_grade -- that field encodes a
    -- school's eventual, fully-built-out grade span, not what it currently
    -- serves (verified: growing schools like Hatch/Rise/Purpose carry a
    -- low_grade years below any student they've ever enrolled). enroll_status
    -- = 0 is "Currently Enrolled" -- this table has no academic_year column,
    -- so status (not a date range) is what scopes it to now. Also filters
    -- out negative grade_level (PowerSchool's own domain for
    -- pre-registration / pre-K, a different, real meaning) so it can never
    -- collide with the scaffold's grade_level = -1 "whole school total"
    -- sentinel, which always comes from gsheet_scaffold below.
    -- Known caveat: a school's very first student in a newly-opening grade
    -- may not be entered in PowerSchool yet even though Finalsite is already
    -- recruiting for that grade -- this scaffold won't carry that grade
    -- until PowerSchool has at least one enrolled student in it.
    current_grade_levels as (
        select distinct schoolid, grade_level,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0 and grade_level >= 0
    ),

    grade_membership as (
        select ps.school_number, ps.abbreviation, ps.region, cgl.grade_level,

        from powerschool_schools as ps
        inner join current_grade_levels as cgl on ps.school_number = cgl.schoolid
    ),

    powerschool_scaffold as (
        select
            gm.school_number as schoolid,
            gm.abbreviation as school,
            gm.region,
            gm.grade_level,

            -- finalsite year toggle: see skill
            2026 as academic_year,

            'KTAF' as org,
            'powerschool' as scaffold_source,

            case
                when gm.grade_level >= 9
                then 'HS'
                when gm.grade_level >= 5
                then 'MS'
                else 'ES'
            end as school_level,

        from grade_membership as gm
    )

    {% if scaffold_source_mode in ("gsheet", "blend") %}
        ,

        -- Scoped to the current cycle so a stale row from a prior year (a
        -- closed school, a dropped grade) doesn't look identical to "PS
        -- doesn't have this yet" and get silently resurrected forever. Miami
        -- must carry its FULL spine here (every school, every grade), not just
        -- -1 rows and net-new entries, since the PowerSchool builder excludes
        -- it entirely above.
        gsheet_scaffold as (
            select
                s.schoolid,
                s.school,
                s.region,
                s.grade_level,
                s.academic_year,
                s.org,
                s.school_level,

                'gsheet' as scaffold_source,

            from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
            -- finalsite year toggle: see skill
            where s.academic_year = 2026
        )
    {% endif %}

{% if scaffold_source_mode == "powerschool" %}

    select
        schoolid,
        school,
        region,
        grade_level,
        academic_year,
        org,
        scaffold_source,
        school_level,
    from powerschool_scaffold

{% elif scaffold_source_mode == "gsheet" %}

    select
        schoolid,
        school,
        region,
        grade_level,
        academic_year,
        org,
        scaffold_source,
        school_level,
    from gsheet_scaffold

{% else %}

    select
        schoolid,
        school,
        region,
        grade_level,
        academic_year,
        org,
        scaffold_source,
        school_level,
    from powerschool_scaffold

    union all

    select
        g.schoolid,
        g.school,
        g.region,
        g.grade_level,
        g.academic_year,
        g.org,
        g.scaffold_source,
        g.school_level,
    from gsheet_scaffold as g
    left join
        powerschool_scaffold as p
        on g.schoolid = p.schoolid
        and g.grade_level = p.grade_level
    where p.schoolid is null

{% endif %}
