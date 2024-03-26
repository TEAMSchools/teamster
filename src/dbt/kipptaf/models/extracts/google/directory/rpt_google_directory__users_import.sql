with
    students as (
        select
            se.first_name as `givenName`,
            se.last_name as `familyName`,
            se.student_email_google as `primaryEmail`,
            se.is_out_of_district,

            o.org_unit_path,

            to_hex(sha1(se.student_web_password)) as `password`,
            if(se.grade_level >= 3, true, false) as `changePasswordAtNextLogin`,
            if(se.enroll_status = 0, false, true) as `suspended`,
            concat(
                'group-students-', lower(se.region), '@teamstudents.org'
            ) as `groupKey`,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        left join
            {{ ref("stg_google_directory__orgunits") }} as o
            on se.school_name = o.description
            and o.org_unit_path like '/Students/%'
        where se.rn_all = 1 and se.student_email_google is not null
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

            if(
                s.suspended or s.is_out_of_district,
                '/Students/Disabled',
                s.org_unit_path
            ) as `orgUnitPath`,

            if(u.primary_email is not null, true, false) as is_matched,
        from students as s
        left join
            {{ ref("stg_google_directory__users") }} as u
            on s.primaryemail = u.primary_email
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
