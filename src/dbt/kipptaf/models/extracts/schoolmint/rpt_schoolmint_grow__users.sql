with
    instructional_managers as (
        select distinct sr.reports_to_employee_number,
        from {{ ref("int_people__staff_roster") }} as sr
        join
            {{ ref("int_people__staff_roster") }} as srm
            on sr.reports_to_employee_number = srm.employee_number
        where
            sr.assignment_status in ('Active', 'Leave')
            and (
                contains_substr(sr.job_title, 'Teacher')
                or contains_substr(sr.job_title, 'Learning Specialist')
            )
            or srm.home_department_name
            in ('School Support', 'Student Support', 'KIPP Forward')
    ),

    people as (
        select
            sr.employee_number as user_internal_id,
            sr.google_email as user_email,
            sr.reports_to_employee_number as manager_internal_id,
            sr.home_work_location_reporting_name as school_name,
            sr.home_department_name as course_name,

            sr.given_name || ' ' || sr.family_name_1 as user_name,

            if(sr.assignment_status in ('Terminated', 'Deceased'), 1, 0) as inactive,

            if(
                sr.primary_grade_level_taught = 0,
                'K',
                cast(sr.primary_grade_level_taught as string)
            ) as grade_abbreviation,

            coalesce(
                case
                    /* network admins */
                    when sr.home_department_name = 'Executive'
                    then ['Sub Admin']
                    when sr.job_title = 'Head of Schools'
                    then ['Regional Admin']
                    when
                        sr.home_department_name in (
                            'Teaching and Learning',
                            'School Support',
                            'New Teacher Development'
                        )
                        and (
                            contains_substr(sr.job_title, 'Chief')
                            or contains_substr(sr.job_title, 'Leader')
                            or contains_substr(sr.job_title, 'Director')
                        )
                    then ['Sub Admin']
                    when sr.job_title = 'Achievement Director'
                    then ['Sub Admin']
                    when
                        sr.home_department_name = 'Special Education'
                        and contains_substr(sr.job_title, 'Director')
                    then ['Sub Admin']
                    when sr.home_department_name = 'Human Resources'
                    then ['Sub Admin']
                    /* school admins */
                    when sr.job_title = 'School Leader'
                    then ['School Admin']
                    when
                        sr.home_department_name = 'School Leadership'
                        and (
                            contains_substr(sr.job_title, 'Assistant School Leader')
                            or contains_substr(sr.job_title, 'Dean')
                            or sr.job_title = 'School Leader in Residence'
                        )
                    then ['School Assistant Admin']
                end,
                /* basic roles: Coach and Teacher are independent; a user can be both */
                array(
                    select rn
                    from
                        unnest(
                            [
                                if(
                                    sr.employee_number in (
                                        select reports_to_employee_number
                                        from instructional_managers
                                    ),
                                    'Coach',
                                    null
                                ),
                                if(
                                    sr.job_title like '%Teacher%'
                                    or sr.job_title like '%Learning%',
                                    'Teacher',
                                    null
                                )
                            ]
                        ) as rn
                    where rn is not null
                )
            ) as role_names,
        from {{ ref("int_people__staff_roster") }} as sr
        where
            sr.user_principal_name is not null
            and sr.home_department_name != 'Data'
            and coalesce(
                sr.worker_termination_date, current_date('{{ var("local_timezone") }}')
            )
            >= '{{ var("current_academic_year") - 1 }}-07-01'
    ),

    people_roles as (
        select
            p.user_internal_id,
            array_agg(rn order by r.role_id) as role_names,
            array_agg(r.role_id order by r.role_id) as role_ids,
        from people as p
        cross join unnest(p.role_names) as rn
        inner join {{ ref("stg_schoolmint_grow__roles") }} as r on rn = r.name
        group by p.user_internal_id
    ),

    roster as (
        select
            p.user_internal_id,
            p.user_name,
            p.user_email,
            p.inactive,

            pra.role_names,
            pra.role_ids,

            sch.school_id,

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

            array(
                select role._id from unnest(u.roles) as role order by role._id
            ) as role_ids_ws,

            if(u.inactive, 1, 0) as inactive_ws,

            case
                when
                    exists (
                        select 1 from unnest(p.role_names) as rn where rn like '%Admin%'
                    )
                then 'observers'
                when 'Coach' in unnest(p.role_names)
                then 'observees;observers'
                else 'observees'
            end as group_type,
        from people as p
        inner join people_roles as pra on p.user_internal_id = pra.user_internal_id
        inner join
            {{ ref("stg_schoolmint_grow__schools") }} as sch on p.school_name = sch.name
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
        from roster
    ),

    surrogate_keys as (
        select
            user_internal_id,
            user_name,
            user_email,
            inactive,
            role_names,
            school_id,
            role_ids,
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
            group_type,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "coach_id",
                        "course_id",
                        "grade_id",
                        "inactive",
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
                        "role_ids_ws_hash",
                        "school_id_ws",
                        "user_email_ws",
                        "user_name_ws",
                    ]
                )
            }} as surrogate_key_destination,
        from roster_hashed
    )

select
    user_internal_id,
    user_name,
    user_email,
    inactive,
    role_names,
    school_id,
    role_ids,
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
    group_type,
    surrogate_key_source,
    surrogate_key_destination,
from surrogate_keys
where
    /* create */
    (inactive = 0 and user_id is null)
    /* archive */
    or (inactive = 1 and user_id is not null and archived_at is null)
    /* update/reactivate */
    or inactive = 0
