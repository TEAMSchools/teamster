with
    students as (
        select
            first_name as `givenName`,
            last_name as `familyName`,
            student_email_google as `primaryEmail`,
            school_name,
            is_out_of_district,

            concat('group-students-', lower(region), '@teamstudents.org') as `groupKey`,

            to_hex(sha1(student_web_password)) as `password`,

            if(grade_level >= 3, true, false) as `changePasswordAtNextLogin`,
            if(enroll_status = 0, false, true) as `suspended`,
        from {{ ref("base_powerschool__student_enrollments") }}
        where rn_all = 1 and student_email_google is not null
    ),

    with_google as (
        select
            s.`primaryEmail`,
            s.`givenName`,
            s.`familyName`,
            s.`groupKey`,
            s.`changePasswordAtNextLogin`,
            s.suspended,
            s.password,

            u.name__given_name as given_name_target,
            u.name__family_name as family_name_target,
            u.suspended as suspended_target,
            u.org_unit_path as org_unit_path_target,

            'SHA-1' as `hashFunction`,

            if(u.primary_email is not null, true, false) as is_matched,

            if(
                s.suspended or s.is_out_of_district,
                '/Students/Disabled',
                o.org_unit_path
            ) as `orgUnitPath`,
        from students as s
        left join
            {{ ref("stg_google_directory__users") }} as u
            on s.primaryemail = u.primary_email
        left join
            {{ ref("stg_google_directory__orgunits") }} as o
            on s.school_name = o.description
            and o.org_unit_path like '/Students/%'
    ),

    final as (
        select
            `primaryEmail`,
            `password`,
            `changePasswordAtNextLogin`,
            `groupKey`,
            `orgUnitPath`,
            `hashFunction`,
            suspended,

            struct(`givenName` as `givenName`, `familyName` as `familyName`) as `name`,
            if(not is_matched and not suspended, true, false) as is_create,
            if(
                is_matched
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
