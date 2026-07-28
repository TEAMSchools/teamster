with
    powerschool_region as (
        select
            sps.school_number,
            sps.abbreviation,
            sps._dbt_source_project,
            {{ extract_region("sps") }} as region,

        from {{ ref("stg_powerschool__schools") }} as sps
        where sps.state_excludefromreporting = 0
    ),

    -- Miami's live SIS is Focus, not PowerSchool -- stg_powerschool__schools'
    -- Miami rows are a frozen pre-migration snapshot, never a source of
    -- truth for current grade membership. Miami's grade membership comes
    -- from the focus_scaffold branch below instead. If another region ever
    -- migrates off PowerSchool, add it to this exclusion list and give it
    -- its own SIS-sourced branch.
    powerschool_schools as (
        select school_number, abbreviation, _dbt_source_project, region,
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
    -- out negative grade_level: PowerSchool uses negative values for its own
    -- pre-registration / pre-K domain, and since this pipeline's convention
    -- is grade_level = -1 means PK, an unfiltered PowerSchool negative row
    -- would masquerade as a legitimate PK enrollment instead of being
    -- excluded as pre-registration noise.
    -- Known caveat: a school's very first student in a newly-opening grade
    -- may not be entered in PowerSchool yet even though Finalsite is already
    -- recruiting for that grade -- this scaffold won't carry that grade
    -- until PowerSchool has at least one enrolled student in it.
    -- Carries _dbt_source_project so grade_membership's join can't collide
    -- across districts on a repeated numeric schoolid -- each PowerSchool
    -- instance assigns schoolid independently, so an excluded/out-of-scope
    -- school in one district can share a schoolid with a reporting school in
    -- another.
    current_grade_levels as (
        select distinct schoolid, grade_level, _dbt_source_project,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0 and grade_level >= 0
    ),

    grade_membership as (
        select ps.school_number, ps.abbreviation, ps.region, cgl.grade_level,

        from powerschool_schools as ps
        inner join
            current_grade_levels as cgl
            on ps.school_number = cgl.schoolid
            and ps._dbt_source_project = cgl._dbt_source_project
    ),

    powerschool_scaffold as (
        select
            gm.school_number as schoolid,
            gm.abbreviation as school,
            gm.region,
            gm.grade_level,

            {{ var("finalsite_recruitment_year") }} as academic_year,

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
    ),

    -- Miami equivalent of current_grade_levels/grade_membership above:
    -- grade membership from actual current enrollment, not a static
    -- school-level grade span. int_focus__student_enrollments (unlike
    -- stg_powerschool__students) carries multiple academic_years, so the
    -- academic_year filter is what scopes this to "currently serves" --
    -- enroll_status = 0 alone isn't enough. Excludes negative grade_level
    -- (-1 = PK, -9 = whole-school total row): neither is SIS grade
    -- membership. ps_schoolid/school_abbreviation are functionally
    -- determined by schoolid, so this DISTINCT is grain projection, not
    -- dup-masking.
    focus_grade_levels as (
        select distinct ps_schoolid, school_abbreviation, region, grade_level,
        from {{ ref("int_focus__student_enrollments") }}
        where
            enroll_status = 0
            and grade_level >= 0
            and academic_year = {{ var("current_academic_year") }}
    ),

    focus_scaffold as (
        select
            fgl.ps_schoolid as schoolid,
            fgl.school_abbreviation as school,
            fgl.region,
            fgl.grade_level,

            {{ var("finalsite_recruitment_year") }} as academic_year,

            'KTAF' as org,
            'focus' as scaffold_source,

            case
                when fgl.grade_level >= 9
                then 'HS'
                when fgl.grade_level >= 5
                then 'MS'
                else 'ES'
            end as school_level,

        from focus_grade_levels as fgl
    ),

    sis_scaffold as (
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
            schoolid,
            school,
            region,
            grade_level,
            academic_year,
            org,
            scaffold_source,
            school_level,
        from focus_scaffold
    ),

    -- Scoped to the current cycle so a stale row from a prior year (a
    -- closed school, a dropped grade) doesn't look identical to "the SIS
    -- doesn't have this yet" and get silently resurrected forever. This
    -- sheet still supplies every school's grade_level = -9 whole-school row
    -- (no SIS branch produces it) and any genuinely new school/grade not
    -- yet live in a SIS -- for Miami that's on top of focus_scaffold above,
    -- not instead of it.
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
        where s.academic_year = {{ var("finalsite_recruitment_year") }}
    )

select
    schoolid,
    school,
    region,
    grade_level,
    academic_year,
    org,
    scaffold_source,
    school_level,
from sis_scaffold

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
    sis_scaffold as p
    on g.region = p.region
    and g.schoolid = p.schoolid
    and g.grade_level = p.grade_level
where p.schoolid is null
