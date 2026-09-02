with
    /* One row: the academic year Miami's SIS became Focus.

       Recorded attendance, not row presence. int_focus__attendance_daily
       scaffolds a present-by-default row for every enrolled student-day back to
       AY2020, so row presence spans AY2020 onward while Focus holds real
       attendance for the cutover year onward only. Presence would put the
       boundary years too early and hand Focus years the PowerSchool archive
       still covers.

       A floor, not a set: `min` cannot punch a hole mid-history the way
       `in (select ...)` can. A Focus year that recorded no exceptions would
       otherwise fall back to an archive holding nothing for it. */
    cutover as (
        select min(academic_year) as focus_start_academic_year,
        from {{ ref("int_focus__attendance_daily") }}
        where is_attendance_recorded
    ),

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
        cross join cutover as cut
        -- Focus carries Miami back to AY2018, which the PowerSchool archive
        -- already covers, so without this gate every pre-cutover Miami year would
        -- land twice. ps_schoolid, not schoolid: the latter is Focus's internal id
        -- and would not share a namespace with the powerschool branch.
        where
            enr.academic_year >= cut.focus_start_academic_year
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
