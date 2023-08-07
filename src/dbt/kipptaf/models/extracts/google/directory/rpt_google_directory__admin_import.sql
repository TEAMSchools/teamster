with
    staff_roster as (
        select
            sr.google_email,
            case
                sr.home_work_location_dagster_code_location
                when 'kippnewark'
                then '/Students/TEAM/'
                when 'kippcamden'
                then '/Students/KCNA/'
                when 'kippmiami'
                then '/Students/Miami/'
            end || case
                sr.home_work_location_powerschool_school_id
                /* TEAM */
                when 133570965
                then 'TEAM Academy'
                when 73252
                then 'Rise'
                when 73253
                then 'NCA'
                when 73254
                then 'SPARK'
                when 73255
                then 'THRIVE'
                when 73256
                then 'Seek'
                when 73257
                then 'Life'
                when 73258
                then 'BOLD'
                when 73259
                then 'Upper Roseville'
                when 732511
                then 'Newark Lab'
                when 732513
                then 'KJA'
                when 732514
                then 'KPA'
                /* KCNA */
                when 179901
                then 'LSP'
                when 179902
                then 'LSM'
                when 179903
                then 'KHM'
                when 179904
                then 'KCNHS'
                when 179905
                then 'KSE'
                /* KMS */
                when 30200803
                then 'Courage'
                when 30200804
                then 'Royalty Academy'
            end as org_unit_path,

            u.id as `assignedTo`,
        from {{ ref("base_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_google_directory__users") }} as u
            on sr.google_email = u.primary_email
        where
            sr.user_principal_name is not null
            and sr.assignment_status not in ('Terminated', 'Deceased')
            and sr.home_work_location_powerschool_school_id != 0
    ),

    with_ids as (
        select
            sr.`assignedTo`,

            r.role_id as `roleId`,

            split(ous.org_unit_id, ":")[1] as `orgUnitId`,
        from staff_roster as sr
        inner join
            {{ ref("stg_google_directory__roles") }} as r
            on r.role_name = 'Reset Student PW'
        inner join
            {{ ref("stg_google_directory__orgunits") }} as ous
            on sr.org_unit_path = ous.org_unit_path
    )

select ids.*, 'ORG_UNIT' as `scopeType`,
from with_ids as ids
left join
    {{ ref("stg_google_directory__role_assignments") }} as ra
    on ids.assignedto = ra.assigned_to
    and ids.roleid = ra.role_id
    and ids.orgunitid = ra.org_unit_id
where ra.role_assignment_id is null
