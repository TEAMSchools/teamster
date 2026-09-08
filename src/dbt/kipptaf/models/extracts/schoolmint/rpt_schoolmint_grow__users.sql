with
    /*
        Read is_current rather than int_people__staff_roster.memberships: that
        string is bucketed by fiscal year, and the prior cohort's 2026-07-01
        expiration lands on day one of the next academic year, so the roster
        string carries last year's coordinators alongside this year's.
    */
    new_teacher_network_coordinators as (
        select distinct associate_id,
        from {{ ref("stg_adp_workforce_now__employee_memberships") }}
        where membership_description = 'New Teacher Network Coordinator' and is_current
    ),

    grow_schools as (
        select
            sch.school_id,
            sch.name as school_name,

            lc.location_dagster_code_location as region,
        from {{ ref("stg_schoolmint_grow__schools") }} as sch
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on sch.name = lc.location_name
        where sch.archived_at is null
    ),

    staff as (
        select
            sr.employee_number,
            sr.google_email,
            sr.reports_to_employee_number,
            sr.home_work_location_reporting_name,
            sr.home_department_name,
            sr.home_work_location_dagster_code_location,
            sr.given_name,
            sr.family_name_1,
            sr.assignment_status,
            sr.primary_grade_level_taught,
            sr.user_principal_name,

            coalesce(
                sr.worker_termination_date, current_date('{{ var("local_timezone") }}')
            ) as active_through,

            coalesce(
                sr.job_function in ('Teacher', 'Teacher in Residence'), false
            ) as is_teacher,

            /* ADP records some Associate Directors at staff level */
            if(
                sr.job_function = 'KTAF or Regional Staff'
                and contains_substr(sr.job_title, 'Associate Director'),
                'KTAF or Regional Director',
                sr.job_function
            ) as tier,

            sr.home_department_name in (
                'Teaching and Learning',
                'School Support',
                'Teacher Development',
                'New Teacher Development',
                'Special Education',
                'School Leadership',
                'Leadership Development',
                'KIPP Forward',
                'Special Projects',
                'Executive'
            ) as passes_department_gate,

            ntnc.associate_id is not null as is_new_teacher_network_coordinator,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            new_teacher_network_coordinators as ntnc on sr.worker_id = ntnc.associate_id
        where sr.home_work_location_dagster_code_location != 'kipppaterson'
    ),

    /* a manager of a teacher, or of anyone in a coaching department, is a Coach */
    instructional_managers as (
        select distinct sr.reports_to_employee_number as employee_number,
        from staff as sr
        inner join staff as srm on sr.reports_to_employee_number = srm.employee_number
        where
            sr.assignment_status in ('Active', 'Leave')
            and (
                sr.is_teacher
                or srm.home_department_name
                in ('School Support', 'Student Support', 'KIPP Forward')
            )
    ),

    /* one boolean per role; every predicate is independent */
    people as (
        select
            sr.employee_number as user_internal_id,
            sr.google_email as user_email,
            sr.reports_to_employee_number as manager_internal_id,
            sr.home_work_location_reporting_name as school_name,
            sr.home_department_name as course_name,
            sr.home_work_location_dagster_code_location as region,
            sr.is_teacher,
            sr.is_new_teacher_network_coordinator as is_regional_observer,

            sr.given_name || ' ' || sr.family_name_1 as user_name,

            im.employee_number is not null as is_coach,

            sr.tier = 'Chief Level' as is_chief,

            sr.tier = 'School Leader' as is_school_admin,

            sr.tier
            in ('Assistant School Leaders', 'Deans') as is_school_assistant_admin,

            sr.tier in (
                'Chief Level',
                'EDs, HOSs, MDOs',
                'KTAF or Regional Managing Director',
                'KTAF or Regional Director'
            )
            and sr.passes_department_gate as is_regional_admin,

            if(sr.assignment_status in ('Terminated', 'Deceased'), 1, 0) as inactive,

            if(
                sr.primary_grade_level_taught = 0,
                'K',
                cast(sr.primary_grade_level_taught as string)
            ) as grade_abbreviation,
        from staff as sr
        left join
            instructional_managers as im on sr.employee_number = im.employee_number
        where
            sr.user_principal_name is not null
            and sr.home_department_name != 'Data'
            and sr.active_through >= '{{ var("current_academic_year") - 1 }}-07-01'
    ),

    /* one slot per role; null slots drop out at the aggregate below */
    people_role_slots as (
        select
            user_internal_id,

            [
                if(is_regional_admin, 'Regional Admin', null),
                if(is_school_admin, 'School Admin', null),
                if(is_school_assistant_admin, 'School Assistant Admin', null),
                if(is_coach, 'Coach', null),
                if(is_regional_observer, 'Regional Observer', null),
                if(is_teacher, 'Teacher', null)
            ] as role_name_slots,
        from people
    ),

    people_roles as (
        select
            p.user_internal_id,

            ifnull(array_agg(rn ignore nulls order by r.role_id), []) as role_names,
            ifnull(
                array_agg(r.role_id ignore nulls order by r.role_id), []
            ) as role_ids,
        from people_role_slots as p
        cross join unnest(p.role_name_slots) as rn
        left join {{ ref("stg_schoolmint_grow__roles") }} as r on rn = r.name
        group by p.user_internal_id
    ),

    regional_scope_schools as (
        /* Regional Admin: Chief Level sees every school, others their region */
        select p.user_internal_id, gs.school_id,
        from people as p
        inner join grow_schools as gs on (p.is_chief or p.region = gs.region)
        where p.is_regional_admin

        union distinct

        /* Regional Observer: their own school only */
        select p.user_internal_id, gs.school_id,
        from people as p
        inner join grow_schools as gs on p.school_name = gs.school_name
        where p.is_regional_observer
    ),

    regional_scope as (
        select user_internal_id, array_agg(school_id order by school_id) as school_ids,
        from regional_scope_schools
        group by user_internal_id
    ),

    roster as (
        select
            p.user_internal_id,
            p.user_name,
            p.user_email,
            p.inactive,

            pra.role_names,
            pra.role_ids,

            gs.school_id,

            u.user_id,
            u.archived_at,
            u.email as user_email_ws,
            u.name as user_name_ws,
            u.default_information_school as school_id_ws,
            u.default_information_grade_level as grade_id_ws,
            u.default_information_course as course_id_ws,
            u.coach as coach_id_ws,

            um.user_id as coach_id,

            cou.tag_id as course_id,

            gr.tag_id as grade_id,

            ifnull(rs.school_ids, []) as regional_admin_school_ids,

            if(p.is_regional_admin, 1, 0) as readonly,

            if(u.read_only, 1, 0) as readonly_ws,

            if(u.inactive, 1, 0) as inactive_ws,

            array(
                select s._id from unnest(u.regional_admin_schools) as s order by s._id
            ) as regional_admin_school_ids_ws,

            array(
                select role._id from unnest(u.roles) as role order by role._id
            ) as role_ids_ws,

            /* observee and observer are independent; a coaching admin is both */
            array_to_string(
                [
                    if(
                        p.is_teacher
                        or p.is_school_admin
                        or p.is_school_assistant_admin,
                        'observees',
                        null
                    ),
                    if(
                        p.is_regional_admin
                        or p.is_regional_observer
                        or p.is_school_admin
                        or p.is_school_assistant_admin
                        or p.is_coach,
                        'observers',
                        null
                    )
                ],
                ';'
            ) as group_type,
        from people as p
        inner join people_roles as pra on p.user_internal_id = pra.user_internal_id
        inner join grow_schools as gs on p.school_name = gs.school_name
        left join regional_scope as rs on p.user_internal_id = rs.user_internal_id
        left join
            {{ ref("stg_schoolmint_grow__users") }} as u
            on p.user_internal_id = u.internal_id_int
        left join
            {{ ref("stg_schoolmint_grow__users") }} as um
            on p.manager_internal_id = um.internal_id_int
        left join
            {{ ref("stg_schoolmint_grow__generic_tags") }} as cou
            on p.course_name = cou.name
            and cou.tag_type = 'courses'
        left join
            {{ ref("stg_schoolmint_grow__generic_tags") }} as gr
            on p.grade_abbreviation = gr.abbreviation
            and gr.tag_type = 'grades'
    ),

    roster_hashed as (
        select
            *,
            array_to_string(role_ids, ',') as role_ids_hash,
            array_to_string(role_ids_ws, ',') as role_ids_ws_hash,
            array_to_string(
                regional_admin_school_ids, ','
            ) as regional_admin_school_ids_hash,
            array_to_string(
                regional_admin_school_ids_ws, ','
            ) as regional_admin_school_ids_ws_hash,

            array_length(role_ids) > 0 as has_roles,
        from roster
    )

select
    user_internal_id,
    user_name,
    user_email,
    inactive,
    role_names,
    school_id,
    role_ids,
    regional_admin_school_ids,
    readonly,
    user_id,
    archived_at,
    user_email_ws,
    user_name_ws,
    school_id_ws,
    grade_id_ws,
    course_id_ws,
    coach_id_ws,
    coach_id,
    course_id,
    grade_id,
    role_ids_ws,
    inactive_ws,
    regional_admin_school_ids_ws,
    readonly_ws,
    group_type,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "coach_id",
                "course_id",
                "grade_id",
                "inactive",
                "readonly",
                "regional_admin_school_ids_hash",
                "role_ids_hash",
                "school_id",
                "user_email",
                "user_name",
            ]
        )
    }} as surrogate_key_source,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "coach_id_ws",
                "course_id_ws",
                "grade_id_ws",
                "inactive_ws",
                "readonly_ws",
                "regional_admin_school_ids_ws_hash",
                "role_ids_ws_hash",
                "school_id_ws",
                "user_email_ws",
                "user_name_ws",
            ]
        )
    }} as surrogate_key_destination,
from roster_hashed
where
    /* a user with no roles and no Grow account has nothing to create or archive */
    (has_roles or user_id is not null)
    and (
        /* create, update, or reactivate */
        inactive = 0
        /* archive */
        or (inactive = 1 and user_id is not null and archived_at is null)
    )
