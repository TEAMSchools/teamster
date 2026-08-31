with
    staff_roster as (
        select
            sr.google_email,

            u.id as user_id,

            x.location_google_student_org_unit_path as org_unit_path,
        from {{ ref("int_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_google_directory__users") }} as u
            on sr.google_email = u.primary_email
        inner join
            {{ ref("int_people__location_crosswalk") }} as x
            on sr.home_work_location_name = x.location_name
        where
            sr.user_principal_name is not null
            and sr.assignment_status not in ('Terminated', 'Deceased')
    ),

    with_ids as (
        select sr.*, r.role_id, split(ous.org_unit_id, ':')[1] as org_unit_id,
        from staff_roster as sr
        inner join
            {{ ref("stg_google_directory__roles") }} as r
            on r.role_name = 'Reset Student PW'
        inner join
            {{ ref("stg_google_directory__orgunits") }} as ous
            on sr.org_unit_path = ous.org_unit_path
    )

select
    ids.google_email,
    ids.org_unit_path,
    ids.user_id as `assignedTo`,
    ids.role_id as `roleId`,
    ids.org_unit_id as `orgUnitId`,

    'ORG_UNIT' as `scopeType`,
from with_ids as ids
left join
    {{ ref("stg_google_directory__role_assignments") }} as ra
    on ids.user_id = ra.assigned_to
    and ids.role_id = ra.role_id
    and ids.org_unit_id = ra.org_unit_id
where ra.role_assignment_id is null
