with
    school_directory as (
        select
            school_number,
            abbreviation,
            _dbt_source_project,

            'KTAF' as org,
            'sis' as scaffold_source,

            {{ extract_region("stg_powerschool__schools") }} as region,

            {{ var("finalsite_recruitment_year") }} as enrollment_academic_year,

        from {{ ref("stg_powerschool__schools") }}
        where state_excludefromreporting = 0 and _dbt_source_project != 'kippmiami'

        union all

        select
            loc.powerschool_school_id as school_number,
            loc.abbreviation,

            f._dbt_source_project,

            'KTAF' as org,
            'sis' as scaffold_source,

            {{ extract_region("f") }} as region,

            {{ var("finalsite_recruitment_year") }} as enrollment_academic_year,

        from {{ ref("int_focus__schools") }} as f
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on f.school_number = loc.focus_school_id
            and not loc.is_pathways
        where f.max_syear is null
    ),

    current_grade_levels as (
        select distinct schoolid, grade_level, _dbt_source_project,

        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0 and _dbt_source_project != 'kippmiami'

        union all

        select distinct ps_schoolid as schoolid, grade_level, _dbt_source_project,

        from {{ ref("int_focus__student_enrollment_roster") }}
        where
            enroll_status = 0
            and academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
    ),

    sis_scaffold as (
        select
            ps.enrollment_academic_year,
            ps.org,
            ps.region,
            ps.school_number as schoolid,
            ps.abbreviation as school,
            ps.scaffold_source,

            cgl.grade_level,

            case
                when cgl.grade_level >= 9
                then 'HS'
                when cgl.grade_level >= 5
                then 'MS'
                else 'ES'
            end as school_level,

        from school_directory as ps
        inner join
            current_grade_levels as cgl
            on ps.school_number = cgl.schoolid
            and ps._dbt_source_project = cgl._dbt_source_project
    ),

    existing_keys as (select region, schoolid, grade_level, from sis_scaffold),

    /* Schools/grades Finalsite is recruiting for that don't exist in
       PowerSchool/Focus yet -- see fresh-dashboard-data-model.md and the
       fresh-dashboard skill's rollover procedure.

       grain projection: school and region are attributes of schoolid,
       school_level is a pure function of grade_level, and the rest are
       literals -- so every selected column is functionally determined by
       (region, schoolid, grade_level); not a mask for upstream duplicates. */
    finalsite_new as (
        select distinct
            u.schoolid,
            u.school,
            u.region,
            u.grade_level,

            'KTAF' as org,
            'finalsite' as scaffold_source,

            case
                when u.grade_level >= 9
                then 'HS'
                when u.grade_level >= 5
                then 'MS'
                else 'ES'
            end as school_level,

            {{ var("finalsite_recruitment_year") }} as enrollment_academic_year,

        from {{ ref("int_finalsite__status_report_unpivot") }} as u
        left join
            existing_keys as k
            on u.region = k.region
            and u.schoolid = k.schoolid
            and u.grade_level = k.grade_level
        where
            u.enrollment_academic_year = {{ var("finalsite_recruitment_year") }}
            and {{ var("finalsite_recruitment_year") }}
            != {{ var("current_academic_year") }}
            and u.schoolid != 0
            and k.schoolid is null
    ),

    selected_scaffold as (
        select
            enrollment_academic_year,
            org,
            region,
            school_level,
            schoolid,
            school,
            grade_level,
            scaffold_source,

        from sis_scaffold

        union all

        select
            enrollment_academic_year,
            org,
            region,
            school_level,
            schoolid,
            school,
            grade_level,
            scaffold_source,

        from finalsite_new
    ),

    school_priority as (
        select
            schoolid,
            school,
            region,
            enrollment_academic_year,
            org,

            min(if(scaffold_source = 'sis', 1, 2)) as source_priority,

        from selected_scaffold
        group by schoolid, school, region, enrollment_academic_year, org
    )

select
    enrollment_academic_year,
    org,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    scaffold_source,

from selected_scaffold

union all

select
    enrollment_academic_year,
    org,
    region,

    cast(null as string) as school_level,

    schoolid,
    school,

    -9 as grade_level,

    if(source_priority = 1, 'sis', 'finalsite') as scaffold_source,

from school_priority

union all

/* grain projection: school_level is functionally determined by
   grade_level alone (same CASE everywhere), so distinct on the region
   grain is safe, not a dup mask. */
select distinct
    enrollment_academic_year,
    org,
    region,
    school_level,

    0 as schoolid,

    region as school,

    grade_level,

    cast(null as string) as scaffold_source,

from selected_scaffold
