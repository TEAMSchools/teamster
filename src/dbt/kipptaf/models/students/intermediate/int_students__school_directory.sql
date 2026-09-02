with
    /* grain projection: student-grain enrollment rows collapsed to one row per
       academic_year/region/schoolid/grade_level -- code_location and
       school_source are functionally determined by that key, so byte-identical
       tuples coalesce. Not a dup mask. */
    powerschool as (
        select distinct
            academic_year,
            region,
            schoolid,
            grade_level,

            _dbt_source_project as code_location,

            'powerschool' as school_source,

        from {{ ref("int_powerschool__student_enrollment_union") }}
        -- No Miami year filter: the frozen archive stops at AY2025 on its own, so
        -- Miami self-terminates here and the Focus branch picks up AY2026 onward.
        -- 999999 is the graduated-students placeholder, not a physical school.
        where schoolid != 999999 and grade_level is not null
    ),

    /* grain projection: the region-years the PowerSchool branch owns, which is
       what makes it authoritative for them below. */
    powerschool_years as (select distinct region, academic_year, from powerschool),

    /* grain projection: same key as the powerschool branch above. */
    focus as (
        select distinct
            enr.academic_year,
            enr.region,
            enr.grade_level,
            enr.ps_schoolid as schoolid,
            enr._dbt_source_project as code_location,

            'focus' as school_source,

        from {{ ref("int_focus__student_enrollment_roster") }} as enr
        -- Anti-join, not a cutover year: Focus carries Miami back to AY2018,
        -- which the PowerSchool archive already covers, so every pre-cutover
        -- Miami year would otherwise land twice and break the grain. Stating it
        -- as precedence -- PowerSchool owns any region-year it has rows for,
        -- Focus fills forward from where the archive stops -- needs no derived
        -- boundary year and stays correct if the archive is ever extended or
        -- Focus backfilled. Verified equivalent to gating on the
        -- attendance-derived cutover year: same 17 rows, zero difference either
        -- direction.
        --
        -- ps_schoolid, not schoolid: the latter is Focus's internal id and would
        -- not share a namespace with the powerschool branch.
        left join
            powerschool_years as psy
            on enr.region = psy.region
            and enr.academic_year = psy.academic_year
        where
            psy.region is null
            and enr.ps_schoolid is not null
            and enr.grade_level is not null
    ),

    enrolled as (
        select
            academic_year, region, schoolid, grade_level, code_location, school_source,

        from powerschool

        union all

        select
            academic_year, region, schoolid, grade_level, code_location, school_source,

        from focus
    ),

    /* Schools and grade levels SRE is recruiting for that no SIS carries yet, so
       the directory can answer "upcoming" as well as previous and current. The
       recruitment-year-vs-current-year predicate is the same gate
       int_tableau__fresh_enrollment_scaffold uses: while the two vars are equal
       this branch is deliberately empty, and bumping finalsite_recruitment_year
       is what turns it on.

       grain projection: the anti-join leaves at most one row per
       region/schoolid/grade_level, and academic_year is a literal. */
    upcoming as (
        select distinct
            u.region,
            u.grade_level,
            u.schoolid,

            {{ var("finalsite_recruitment_year") }} as academic_year,

            'finalsite' as school_source,

            'kipp' || lower(u.region) as code_location,

        from {{ ref("int_finalsite__status_report_unpivot") }} as u
        left join
            enrolled as e
            on u.region = e.region
            and u.schoolid = e.schoolid
            and u.grade_level = e.grade_level
        where
            u.enrollment_academic_year = {{ var("finalsite_recruitment_year") }}
            and {{ var("finalsite_recruitment_year") }}
            != {{ var("current_academic_year") }}
            and u.schoolid != 0
            and u.grade_level is not null
            and e.schoolid is null
    )

select academic_year, region, schoolid, grade_level, code_location, school_source,

from enrolled

union all

select academic_year, region, schoolid, grade_level, code_location, school_source,

from upcoming
