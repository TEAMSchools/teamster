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
            sps.school_number,
            sps.abbreviation,
            sps.low_grade,
            sps.high_grade,

            {{ extract_region("sps") }} as region,

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
        select school_number, abbreviation, low_grade, high_grade, region,
        from powerschool_region
        where region != 'Miami'
    ),

    -- Filters out any negative grade_level (PowerSchool's own domain for
    -- pre-registration / pre-K, a different, real meaning) before it can
    -- ever reach the scaffold's grade_level = -1 "whole school total"
    -- sentinel -- without this, a school with a negative low_grade would
    -- produce a real PowerSchool-sourced -1 row indistinguishable from
    -- that sentinel. The -1 row always comes from gsheet_scaffold below.
    grade_expansion as (
        select school_number, abbreviation, region, grade_level,

        from powerschool_schools
        cross join unnest(generate_array(low_grade, high_grade)) as grade_level
        where grade_level >= 0
    ),

    powerschool_scaffold as (
        select
            ge.school_number as schoolid,
            ge.abbreviation as school,
            ge.region,
            ge.grade_level,

            cy.academic_year,

            'KTAF' as org,
            'powerschool' as scaffold_source,

            case
                when ge.grade_level >= 9
                then 'HS'
                when ge.grade_level >= 5
                then 'MS'
                else 'ES'
            end as school_level,

        from grade_expansion as ge
        cross join {{ ref("int_finalsite__current_academic_year") }} as cy
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
            inner join
                {{ ref("int_finalsite__current_academic_year") }} as cy
                on s.academic_year = cy.academic_year
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
