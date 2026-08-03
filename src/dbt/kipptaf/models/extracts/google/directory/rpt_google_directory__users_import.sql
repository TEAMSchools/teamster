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
        where rn_all = 1 and student_email is not null and region != 'Miami'
    ),

    finalsite_enrolled as (
        /* Finalsite is the admissions front door, so a newly enrolled student
        appears here before they are imported into Focus. Sourcing them here too
        means their account exists by the time that first import runs. */
        select
            l.finalsite_enrollment_id,
            l.assigned_school,
            l.is_transfer_out,

            cast(ida.focus_student_id_prefixed as int64) as student_number,

            regexp_extract(l.grade_canonical_name, r'\d+') as grade_digits,
        from {{ ref("int_finalsite__enrollment_lifecycle") }} as l
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on l.finalsite_enrollment_id = ida.finalsite_enrollment_id
        where
            l.school_year_start = {{ var("current_academic_year") }}
            and l.assigned_school is not null
            and l._dbt_source_project = 'kippmiami'
    ),

    focus_ranked as (
        /* Rank every stint, not just the current year's. The PowerSchool branch
        uses rn_all, so restricting Focus to the current academic year would hide
        a student whose last stint predates it -- their account could never be
        suspended. Ordering matches int_powerschool__student_enrollment_union. */
        select
            student_number,
            student_first_name,
            student_last_name,
            school,
            grade_level,
            region,
            enroll_status,
            academic_year,

            row_number() over (
                partition by student_number order by academic_year desc, exitdate desc
            ) as rn_all,
        from {{ ref("int_focus__student_enrollments") }}
    ),

    focus_students as (
        /* Miami's PowerSchool is a frozen archive, so Focus is the enrollment
        source. The address comes from the login generator rather than from
        Focus, so provisioning does not wait on the import-once DEMOGRAPHICS
        feed that still owes ~420 enrolled students an address (#4698). */
        select
            r.student_number,
            r.student_first_name as first_name,
            r.student_last_name as last_name,
            r.school as school_name,
            r.grade_level,

            sl.google_email as student_email_google,
            sl.default_password as student_web_password,

            /* Focus surfaces no out-of-district placement field; routing is on
            suspension alone. If a Miami student is ever placed out of district
            they will keep an active account instead of moving to
            /Students/Disabled -- see the note on #4513. */
            false as is_out_of_district,

            lower(r.region) as region,

            if(r.enroll_status = 0, false, true) as suspended,
        from focus_ranked as r
        inner join
            {{ ref("stg_people__student_logins") }} as sl
            on r.student_number = sl.student_number
        left join finalsite_enrolled as fe on r.student_number = fe.student_number
        /* A stale Focus stint must not outrank a live Finalsite enrollment. A
        returning student whose last Focus stint is a prior year, but who is
        enrolled again for the current year, is dropped here and picked up by
        finalsite_students as active -- otherwise the prior year's withdrawal
        would suspend an account that should stay open. */
        where
            r.rn_all = 1
            and (
                r.academic_year = {{ var("current_academic_year") }}
                or fe.student_number is null
            )
    ),

    finalsite_students as (
        select
            e.student_number,
            e.is_transfer_out as suspended,

            c.first_name,
            c.last_name,

            /* assigned_school carries the Finalsite spelling, which does not
            always match the Google org unit description (KIPP Miami Tech vs
            KIPP Miami Technical High). The crosswalk normalizes it. */
            x.location_clean_name as school_name,

            sl.google_email as student_email_google,
            sl.default_password as student_web_password,

            false as is_out_of_district,

            /* the lifecycle model is scoped to kippmiami above */
            'miami' as region,

            if(e.grade_digits is null, 0, cast(e.grade_digits as int64)) as grade_level,
        from finalsite_enrolled as e
        inner join
            {{ ref("stg_finalsite__contacts") }} as c
            on e.finalsite_enrollment_id = c.finalsite_enrollment_id
        inner join
            {{ ref("int_people__location_crosswalk") }} as x
            on e.assigned_school = x.location_name
        inner join
            {{ ref("stg_people__student_logins") }} as sl
            on e.student_number = sl.student_number
        left join focus_students as f on e.student_number = f.student_number
        where f.student_number is null
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
        from finalsite_students
    ),

    with_google as (
        /* The org unit is named explicitly in the people__locations sheet rather
        than matched against the org unit's free-text description. The three
        branches above carry three different school-name vocabularies -- Focus
        and Finalsite resolve to the sheet's name, PowerSchool keeps its own
        (KIPP Hatch Academy vs the sheet's KIPP Hatch Middle) -- and the
        crosswalk maps every one of them to the same row, since each row there
        is one alias. Joining stg_google_directory__orgunits on the sheet's path
        keeps it honest: a path that does not exist in Google resolves to null
        and the student drops out below rather than being sent with a bad
        orgUnitPath. */
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
            {{ ref("int_people__location_crosswalk") }} as x
            on s.school_name = x.location_name
        left join
            {{ ref("stg_google_directory__orgunits") }} as o
            on x.location_google_student_org_unit_path = o.org_unit_path
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
/* A null org unit means the school has no student org unit named in the
locations sheet. Dropping those students is deliberate -- provisioning an
account with no orgUnitPath would file it at the domain root. */
where (is_create or is_update) and org_unit_path is not null
