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
    -- work_assignment_key is dim_staff_work_assignments' own surrogate PK
    -- (globally unique), so ordering by it alone is already a fully
    -- deterministic pick -- no additional tiebreaker needed.
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

            -- Explicit allow-list. An unrecognized or NULL business unit resolves
            -- to 'unknown' (a deny sentinel) rather than 'Region': 'unknown'
            -- matches only entity-agnostic 'any' role rows in the crosswalk, never
            -- the entity-specific KTAF/Region grants (e.g. Region's region-wide
            -- student scope). Prevents fail-toward-grant on an unresolved org unit.
            case
                o.business_unit_name
                when 'KIPP TEAM and Family Schools Inc.'
                then 'KTAF'
                when 'TEAM Academy Charter School'
                then 'Region'
                when 'KIPP Cooper Norcross Academy'
                then 'Region'
                when 'KIPP Miami'
                then 'Region'
                when 'KIPP Paterson'
                then 'Region'
                else 'unknown'
            end as entity,
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
        from current_assignment as ca
        left join
            {{ ref("stg_google_sheets__people__cube_access_department_rollup") }} as dr
            on ca.department_name = dr.department_name
    ),

    -- Rank the crosswalk role rows so a specific-entity match beats the 'any'
    -- wildcard, then keep 1 per staff member (`role_picked`). The rank prevents
    -- a fan-out when the sheet carries both a wildcard and a specific row for
    -- one `job_function_code`. A LEFT-join miss yields 1 null-role row at
    -- `role_rank` 1, which coalesces to 'none' downstream.
    role_ranked as (
        select
            e.staff_key,

            rl.job_function_level,
            rl.student_location_scope,
            rl.staff_location_scope,
            rl.staff_department_scope,
            rl.staff_pii_scope,
            rl.staff_compensation_scope,
            rl.staff_observations_scope,
            rl.staff_benefits_scope,

            row_number() over (
                partition by e.staff_key order by if(rl.entity = e.entity, 0, 1)
            ) as role_rank,
        from enriched as e
        left join
            {{ ref("stg_google_sheets__people__cube_access_role") }} as rl
            on e.job_function_code = rl.job_function_code
            and rl.entity in ('any', e.entity)
    ),

    role_picked as (select *, from role_ranked where role_rank = 1),

    -- Individual exceptions live for this run: status active, not before
    -- grant_date, not past expiry_date. Every other row (revoked, expired,
    -- not-yet-granted) is excluded entirely -- it contributes nothing below,
    -- exactly as if it didn't exist.
    individual_exceptions_live as (
        select
            additional_location_name,
            google_email,

            -- The sheet spells "leave this alone" as 'inherit' so a form can
            -- require every cell and a reader can tell a deliberate no from an
            -- unfilled one. NULL is what the coalesce chain below reads as
            -- fall-through, so the translation happens here, once, before the
            -- max() in individual_exception_scopes -- which would otherwise
            -- pick the literal 'inherit' over a real override.
            nullif(staff_department_scope, 'inherit') as staff_department_scope,
            nullif(staff_pii_scope, 'inherit') as staff_pii_scope,
            nullif(staff_compensation_scope, 'inherit') as staff_compensation_scope,
            nullif(staff_observations_scope, 'inherit') as staff_observations_scope,
            nullif(staff_benefits_scope, 'inherit') as staff_benefits_scope,

            -- additional_location_scope is already constrained to
            -- network/region/school by the staging accepted_values test, and a
            -- null (remit-only row) is filtered out downstream (where
            -- location_scope != 'none') before this could ever resolve to
            -- 'none' -- a plain coalesce, not a case, is enough.
            coalesce(additional_location_scope, 'none') as location_scope,

            -- Which axes this row's location reaches. Independent per axis: a
            -- row may widen students without staff, or the reverse. 'none' is
            -- the sheet's word for "not this axis"; it is never blank, so a
            -- plain inequality is the whole test.
            additional_student_location_scope != 'none' as includes_student_data,
            additional_staff_location_scope != 'none' as includes_staff_data,
        from {{ ref("stg_google_sheets__people__cube_access_individual_exceptions") }}
        where {{ is_live_row("status", "grant_date", "expiry_date") }}
    ),

    -- At most one live row per grantee sets these (enforced by
    -- test_cube_access_individual_exceptions_single_remit_row), so max() is a
    -- safe deterministic pick, not an arbitrary one.
    individual_exception_scopes as (
        select
            google_email,
            max(staff_department_scope) as staff_department_scope,
            max(staff_pii_scope) as staff_pii_scope,
            max(staff_compensation_scope) as staff_compensation_scope,
            max(staff_observations_scope) as staff_observations_scope,
            max(staff_benefits_scope) as staff_benefits_scope,
        from individual_exceptions_live
        group by google_email
    ),

    -- One struct per live location-grant row, array_agg'd per employee so this
    -- mart keeps its 1-row-per-staff_key grain while carrying however many
    -- grants that person has. access.js unions the abbreviations from every
    -- element (see src/cube/access.js and src/cube/CLAUDE.md).
    individual_exception_grants as (
        select
            iel.google_email,
            array_agg(
                struct(
                    iel.location_scope,
                    reg.region_key,
                    loc.abbreviation as location_abbreviation,
                    iel.includes_student_data,
                    iel.includes_staff_data
                )
            ) as additional_location_grants,
        from individual_exceptions_live as iel
        left join
            {{ ref("dim_regions") }} as reg
            on iel.additional_location_name = reg.legal_entity
        left join
            {{ ref("dim_locations") }} as loc
            on iel.additional_location_name = loc.`name`
        where iel.location_scope != 'none'
        group by iel.google_email
    ),

    -- Contractors and anyone else granted access without an employment record.
    -- They hold a KTAF Google login but no ADP work assignment, so the spine
    -- above emits nothing for them and their grant rows would join to nothing.
    -- This leg gives them a row of their own. The directory join is the
    -- authorization check: the address must be a real Google account, and one
    -- that is neither suspended nor archived, so a typo or a deprovisioned
    -- contractor cannot mint an identity. Minting is deliberately ungated on
    -- location_scope: a remit-only grant row carries no location, and
    -- test_cube_access_individual_exceptions_grant_reaches_a_viewer requires
    -- every live row to resolve to a viewer. A row that grants nothing
    -- therefore yields a viewer who is denied everything -- is_employee below
    -- is what keeps that viewer out of the open staff directory.
    non_employee_grantees as (
        select distinct
            {{
                dbt_utils.generate_surrogate_key(
                    ["'non_employee'", "iel.google_email"]
                )
            }} as staff_key, iel.google_email,
        from individual_exceptions_live as iel
        inner join
            {{ ref("stg_google_directory__users") }} as u
            on iel.google_email = lower(u.primary_email)
            and not coalesce(u.suspended, false)
            and not coalesce(u.archived, false)
        left join enriched as e on iel.google_email = e.google_email
        where e.google_email is null
    ),

    -- Both kinds of viewer on one grain, so the resolution below is written
    -- once. The staff leg carries its role and org attributes; the non-employee
    -- leg carries NULLs, which the coalesces read as 'none'. entity is the
    -- exception: 'unknown' is its deny sentinel, and the column is never NULL.
    access_spine as (
        select
            staff_key,
            google_email,
            department_name,
            department_group,
            entity,
            job_function_code,
            region_key,
            location_abbreviation,

            true as is_employee,
        from enriched

        union all

        select
            staff_key,
            google_email,
            cast(null as string) as department_name,
            cast(null as string) as department_group,
            'unknown' as entity,
            cast(null as string) as job_function_code,
            cast(null as string) as region_key,
            cast(null as string) as location_abbreviation,

            false as is_employee,
        from non_employee_grantees
    ),

    matched as (
        select
            e.staff_key,
            e.google_email,
            e.region_key,
            e.location_abbreviation,
            e.department_group,
            e.entity,
            e.job_function_code,
            e.is_employee,

            rp.job_function_level,

            coalesce(
                ovr.student_location_scope, rp.student_location_scope, 'none'
            ) as student_location_scope,

            coalesce(
                ovr.staff_location_scope, rp.staff_location_scope, 'none'
            ) as staff_location_scope,
            coalesce(
                iex.staff_department_scope,
                ovr.staff_department_scope,
                rp.staff_department_scope,
                'none'
            ) as staff_department_scope,
            coalesce(
                iex.staff_pii_scope, ovr.staff_pii_scope, rp.staff_pii_scope, 'none'
            ) as staff_pii_scope,
            coalesce(
                iex.staff_compensation_scope,
                ovr.staff_compensation_scope,
                rp.staff_compensation_scope,
                'none'
            ) as staff_compensation_scope,
            coalesce(
                iex.staff_observations_scope,
                ovr.staff_observations_scope,
                rp.staff_observations_scope,
                'none'
            ) as staff_observations_scope,
            coalesce(
                iex.staff_benefits_scope,
                ovr.staff_benefits_scope,
                rp.staff_benefits_scope,
                'none'
            ) as staff_benefits_scope,

            coalesce(ieg.additional_location_grants, []) as additional_location_grants,
        from access_spine as e
        left join
            individual_exception_scopes as iex on e.google_email = iex.google_email
        left join
            individual_exception_grants as ieg on e.google_email = ieg.google_email
        left join
            {{ ref("stg_google_sheets__people__cube_access_department_override") }}
            as ovr
            on e.department_name = ovr.department
        left join role_picked as rp on e.staff_key = rp.staff_key
    )

select
    staff_key,
    google_email,
    region_key,
    location_abbreviation,
    department_group,
    entity,
    job_function_code,
    job_function_level,
    is_employee,

    student_location_scope,

    staff_location_scope,
    staff_department_scope,
    staff_pii_scope,
    staff_compensation_scope,
    staff_observations_scope,
    staff_benefits_scope,

    additional_location_grants,
from matched
