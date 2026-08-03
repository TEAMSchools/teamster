with
    powerschool_students as (
        select
            student_number,
            student_first_name as first_name,
            student_last_name as last_name,
            school_name,
            grade_level,
            student_email as student_email_google,
            student_web_password,
            is_out_of_district,

            lower(region) as region,

            if(enroll_status = 0, false, true) as suspended,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            rn_all = 1
            and student_email is not null
            and region not in ('Paterson', 'Miami')
    ),

    focus_students as (
        /* Miami's PowerSchool is a frozen archive, so Focus is the enrollment
        source. The address comes from the login generator rather than from
        Focus, so provisioning does not wait on the import-once DEMOGRAPHICS
        feed that still owes ~420 enrolled students an address (#4698). */
        select
            e.student_number,
            e.student_first_name as first_name,
            e.student_last_name as last_name,
            e.school as school_name,
            e.grade_level,

            sl.google_email as student_email_google,
            sl.default_password as student_web_password,

            /* Focus surfaces no out-of-district placement field; routing is on
            suspension alone. If a Miami student is ever placed out of district
            they will keep an active account instead of moving to
            /Students/Disabled -- see the note on #4513. */
            false as is_out_of_district,

            lower(e.region) as region,

            if(e.enroll_status = 0, false, true) as suspended,
        from {{ ref("int_focus__student_enrollments") }} as e
        inner join
            {{ ref("stg_people__student_logins") }} as sl
            on e.student_number = sl.student_number
        where e.academic_year = {{ var("current_academic_year") }} and e.rn_year = 1
    ),

    students as (
        select
            student_number,
            first_name,
            last_name,
            school_name,
            grade_level,
            student_email_google,
            student_web_password,
            is_out_of_district,
            region,
            suspended,
        from powerschool_students

        union all

        select
            student_number,
            first_name,
            last_name,
            school_name,
            grade_level,
            student_email_google,
            student_web_password,
            is_out_of_district,
            region,
            suspended,
        from focus_students
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
    student_number,

    'SHA-1' as `hashFunction`,

    'group-students-' || region || '@teamstudents.org' as `groupKey`,

    struct(first_name as `givenName`, last_name as `familyName`) as `name`,
    to_hex(sha1(student_web_password)) as `password`,

    if(grade_level >= 3, true, false) as `changePasswordAtNextLogin`,
from final
where is_create or is_update
