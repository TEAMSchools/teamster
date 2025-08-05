with
    students as (
        select
            first_name,
            last_name,
            school_name,
            grade_level,
            student_email_google,
            student_web_password,
            is_out_of_district,

            lower(region) as region,

            if(enroll_status = 0, false, true) as suspended,
        from {{ ref("base_powerschool__student_enrollments") }}
        where rn_all = 1 and student_email_google is not null
    ),

    with_google as (
        select
            s.*,

            u.surrogate_key_target,

            if(u.primary_email is not null, true, false) as is_matched,

            if(
                s.suspended or s.is_out_of_district,
                '/Students/Disabled',
                o.org_unit_path
            ) as org_unit_path,
        from students as s
        left join
            {{ ref("stg_google_directory__users") }} as u
            on s.student_email_google = u.primary_email
        left join
            {{ ref("stg_google_directory__orgunits") }} as o
            on s.school_name = o.description
            and o.org_unit_path like '/Students/%'
    ),

    final as (
        select
            *,

            if(not is_matched and not suspended, true, false) as is_create,

            if(
                is_matched
                and {{
                    dbt_utils.generate_surrogate_key(
                        ["first_name", "last_name", "suspended", "org_unit_path"]
                    )
                }} != surrogate_key_target,
                true,
                false
            ) as is_update,
        from with_google
    )

select
    student_email_google as `primaryEmail`,
    org_unit_path as `orgUnitPath`,
    suspended,
    is_create,
    is_update,

    'SHA-1' as `hashFunction`,

    'group-students-' || region || '@teamstudents.org' as `groupKey`,

    struct(first_name as `givenName`, last_name as `familyName`) as `name`,
    to_hex(sha1(student_web_password)) as `password`,

    if(grade_level >= 3, true, false) as `changePasswordAtNextLogin`,
from final
where is_create or is_update
