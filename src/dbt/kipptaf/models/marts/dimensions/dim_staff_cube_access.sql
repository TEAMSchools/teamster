{#-
  One row per active, primary staff member, keyed on staff_key. Resolves each
  person's current role to the Cube access model: the student location scopes,
  the staff sensitive-field remit (location + department), and the per-field
  sensitive scopes. Read by Cube's contextToGroups (by google_email) to build
  the access group list and the queryRewrite filters; not exposed as a Cube.
  Assembled intra-mart from the current primary work assignment; mappings come
  from the Google Sheets crosswalks (department override wins over the role
  mapping). entity (KTAF/Region) is derived from business_unit_name. The viewer
  identity keys (region_key, location_abbreviation, department_group) are carried
  so cube.js builds location/department filters from the scope level. Rows that
  resolve to no role emit 'none' (deny) rather than NULL.
-#}
with
    -- one current primary work assignment per staff (dedup'd below)
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    primary_assignment as (
        select swa.staff_key, swa.work_assignment_key,
        from {{ ref("dim_staff_work_assignments") }} as swa
        inner join
            {{ ref("dim_work_assignment_primary") }} as p
            on swa.work_assignment_key = p.work_assignment_key
            and p.is_current
            and p.is_primary_position
        where swa.is_current and swa.staff_key is not null
    ),

    -- TODO: a few staff carry two concurrent current primary work assignments;
    -- pick one deterministically until the upstream ADP data is corrected.
    primary_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="primary_assignment",
                partition_by="staff_key",
                order_by="work_assignment_key asc",
            )
        }}
    ),

    -- spine on the current primary assignment (is_current already excludes
    -- terminated staff via termination date, so no status filter is needed);
    -- one row per active staff. Attributes left-join from the assignment's child
    -- dims, NULL (→ deny) where a dimension does not resolve.
    current_assignment as (
        select
            pd.staff_key,

            s.google_email,

            j.job_function_code,

            o.department_name,
            o.business_unit_name,

            loc.region_key,
            loc.abbreviation as location_abbreviation,

            if(
                o.business_unit_name = 'KIPP TEAM and Family Schools Inc.',
                'KTAF',
                'Region'
            ) as entity,
        from primary_deduped as pd
        inner join {{ ref("dim_staff") }} as s on pd.staff_key = s.staff_key
        left join
            {{ ref("dim_work_assignment_jobs") }} as j
            on pd.work_assignment_key = j.work_assignment_key
            and j.is_current
        left join
            {{ ref("dim_work_assignment_organizational_units") }} as o
            on pd.work_assignment_key = o.work_assignment_key
            and o.is_current
            and o.assignment_type = 'home'
        left join
            {{ ref("dim_work_assignment_locations") }} as wal
            on pd.work_assignment_key = wal.work_assignment_key
            and wal.is_current
        left join
            {{ ref("dim_locations") }} as loc on wal.location_key = loc.location_key
    ),

    enriched as (
        select
            ca.staff_key,
            ca.google_email,
            ca.job_function_code,
            ca.department_name,
            ca.entity,
            ca.region_key,
            ca.location_abbreviation,

            dr.department_group,
            dr.department_type,
        from current_assignment as ca
        left join
            {{ ref("stg_google_sheets__people__cube_access_department_rollup") }} as dr
            on ca.department_name = dr.department_name
    ),

    matched as (
        select
            e.staff_key,
            e.google_email,
            e.region_key,
            e.location_abbreviation,
            e.department_group,
            e.department_type,
            e.entity,
            e.job_function_code,

            rl.job_function_level,

            coalesce(
                ovr.student_summary_location_scope,
                rl.student_summary_location_scope,
                'none'
            ) as student_summary_location_scope,
            coalesce(
                ovr.student_detail_location_scope,
                rl.student_detail_location_scope,
                'none'
            ) as student_detail_location_scope,
            coalesce(
                ovr.student_pii_scope, rl.student_pii_scope, 'none'
            ) as student_pii_scope,

            coalesce(
                ovr.staff_location_scope, rl.staff_location_scope, 'none'
            ) as staff_location_scope,
            coalesce(
                ovr.staff_department_scope, rl.staff_department_scope, 'none'
            ) as staff_department_scope,
            coalesce(
                ovr.staff_pii_scope, rl.staff_pii_scope, 'none'
            ) as staff_pii_scope,
            coalesce(
                ovr.staff_compensation_scope, rl.staff_compensation_scope, 'none'
            ) as staff_compensation_scope,
            coalesce(
                ovr.staff_observations_scope, rl.staff_observations_scope, 'none'
            ) as staff_observations_scope,
            coalesce(
                ovr.staff_benefits_scope, rl.staff_benefits_scope, 'none'
            ) as staff_benefits_scope,
        from enriched as e
        left join
            {{ ref("stg_google_sheets__people__cube_access_department_override") }}
            as ovr
            on e.department_name = ovr.department
        left join
            {{ ref("stg_google_sheets__people__cube_access_role") }} as rl
            on e.job_function_code = rl.job_function_code
            and rl.entity in ('any', e.entity)
            and rl.department_type in ('any', e.department_type)
    )

select
    staff_key,
    google_email,
    region_key,
    location_abbreviation,
    department_group,
    department_type,
    entity,
    job_function_code,
    job_function_level,

    student_summary_location_scope,
    student_detail_location_scope,
    student_pii_scope,

    staff_location_scope,
    staff_department_scope,
    staff_pii_scope,
    staff_compensation_scope,
    staff_observations_scope,
    staff_benefits_scope,
from matched
