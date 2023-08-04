with
    students as (
        select
            first_name as given_name,
            last_name as family_name,
            student_web_password as `password`,
            student_email_google as primary_email,
            concat(
                'group-students-', lower(region), '@teamstudents.org'
            ) as group_email,
            case when grade_level >= 3 then 'on' else 'off' end as changepassword,
            case when enroll_status = 0 then false else true end as suspended,
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
        where rn_all = 1
    ),

    with_google as (
        select
            s.primary_email,
            s.given_name,
            s.family_name,
            s.password,
            s.changepassword,
            s.suspended,
            s.group_email,
            concat(
                '/Students/',
                case
                    when s.suspended
                    then 'Disabled'
                    when s.ou_school_name = 'Out of District'
                    then 'Disabled'
                    else s.ou_region || '/' || s.ou_school_name
                end
            ) as org_unit_path,

            u.name__given_name as given_name_target,
            u.name__family_name as family_name_target,
            u.suspended as suspended_target,
            u.org_unit_path as org_unit_path_target,

            if(not s.suspended and u.primary_email is null, true, false) as is_create,
        from students as s
        left join
            {{ ref("stg_google_directory__users") }} as u
            on s.student_email_google = u.primary_email
    )

select
    *,
    if(
        not is_create
        and {{
            dbt_utils.generate_surrogate_key(
                ["given_name", "family_name", "suspended", "org_unit_path"]
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
