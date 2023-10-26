with
    students as (
        select
            first_name as `givenName`,
            last_name as `familyName`,
            student_email_google as `primaryEmail`,
            to_hex(sha1(student_web_password)) as `password`,
            concat('group-students-', lower(region), '@teamstudents.org') as `groupKey`,
            if(grade_level >= 3, true, false) as `changePasswordAtNextLogin`,
            if(enroll_status = 0, false, true) as `suspended`,
            case
                region
                when 'Newark'
                then 'TEAM'
                when 'Camden'
                then 'KCNA'
                when 'Miami'
                then 'Miami'
            end as ou_region,
            if(
                is_out_of_district,
                'Out of District',
                case
                    school_abbreviation
                    when 'KHS'
                    then 'KCNHS'
                    when 'Hatch'
                    then 'KHM'
                    when 'Sumner'
                    then 'KSE'
                    when 'Royalty'
                    then 'Royalty Academy'
                    when 'Justice'
                    then 'KJA'
                    when 'Purpose'
                    then 'KPA'
                    when 'NLH'
                    then 'Newark Lab'
                    when 'TEAM'
                    then 'TEAM Academy'
                    when 'KURA'
                    then 'Upper Roseville'
                    else school_abbreviation
                end
            ) as ou_school_name,
        from {{ ref("base_powerschool__student_enrollments") }}
        where rn_all = 1 and student_email_google is not null
    ),

    with_google as (
        select
            s.`primaryEmail`,
            s.`givenName`,
            s.`familyName`,
            s.`suspended`,
            s.`password`,
            s.`changePasswordAtNextLogin`,
            s.`groupKey`,

            u.name__given_name as given_name_target,
            u.name__family_name as family_name_target,
            u.suspended as suspended_target,
            u.org_unit_path as org_unit_path_target,

            'SHA-1' as `hashFunction`,

            concat(
                '/Students/',
                case
                    when s.`suspended`
                    then 'Disabled'
                    when s.ou_school_name = 'Out of District'
                    then 'Disabled'
                    else s.ou_region || '/' || s.ou_school_name
                end
            ) as `orgUnitPath`,
            if(u.primary_email is not null, true, false) as `matched`,
        from students as s
        left join
            {{ ref("stg_google_directory__users") }} as u
            on s.`primaryEmail` = u.primary_email
    ),

    final as (
        select
            `primaryEmail`,
            `suspended`,
            `password`,
            `changePasswordAtNextLogin`,
            `groupKey`,
            `orgUnitPath`,
            `hashFunction`,
            struct(`givenName` as `givenName`, `familyName` as `familyName`) as `name`,
            if(not `matched` and not suspended, true, false) as is_create,
            if(
                `matched`
                and {{
                    dbt_utils.generate_surrogate_key(
                        ["givenName", "familyName", "suspended", "orgUnitPath"]
                    )
                }}
                !={{
                    dbt_utils.generate_surrogate_key(
                        [
                            "given_name_target",
                            "family_name_target",
                            "suspended_target",
                            "org_unit_path_target",
                        ]
                    )
                }},
                true,
                false
            ) as is_update,
        from with_google
    )

select *,
from final
where is_create or is_update
