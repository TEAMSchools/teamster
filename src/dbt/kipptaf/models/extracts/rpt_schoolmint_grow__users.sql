with
    people as (
        select
            sr.employee_number as user_internal_id,
            sr.google_email as user_email,
            sr.reports_to_employee_number as manager_internal_id,
            sr.home_work_location_name as school_name,
            sr.home_department_name as course_name,

            sr.given_name || ' ' || sr.family_name_1 as user_name,

            if(sr.assignment_status in ('Terminated', 'Deceased'), 1, 0) as inactive,

            if(
                tgl.grade_level = 0, 'K', cast(tgl.grade_level as string)
            ) as grade_abbreviation,

            case
                /* network admins */
                when sr.home_department_name = 'Executive'
                then 'Sub Admin'
                when sr.job_title = 'Head of Schools'
                then 'Regional Admin'
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
                then 'Sub Admin'
                when
                    sr.home_department_name = 'Special Education'
                    and contains_substr(sr.job_title, 'Director')
                then 'Sub Admin'
                when sr.home_department_name = 'Human Resources'
                then 'Sub Admin'
                /* school admins */
                when sr.job_title = 'School Leader'
                then 'School Admin'
                when
                    sr.home_department_name = 'School Leadership'
                    and (
                        contains_substr(sr.job_title, 'Assistant School Leader')
                        or contains_substr(sr.job_title, 'Dean')
                    )
                then 'School Assistant Admin'
                /* basic roles */
                when
                    sr.management_position_indicator
                    and (
                        sr.job_title like '%Teacher%'
                        or sr.job_title like '%Learning%'
                        or sr.department_home_name
                        in ('School Support', 'Student Support', 'KIPP Forward')
                    )
                then 'Coach'
                when (sr.job_title like '%Teacher%' or sr.job_title like '%Learning%')
                then 'Teacher'
            end as role_name,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
            on sr.powerschool_teacher_number = tgl.teachernumber
            and tgl.academic_year = {{ var("current_academic_year") }}
            and tgl.grade_level_rank = 1
        where
            sr.user_principal_name is not null
            and sr.home_department_name != 'Data'
            and coalesce(
                sr.worker_termination_date, current_date('{{ var("local_timezone") }}')
            )
            >= date({{ var("current_academic_year") - 1 }}, 7, 1)
    ),

    roster as (
        select
            p.user_internal_id,
            p.user_name,
            p.user_email,
            p.inactive,
            p.role_name,

            r.role_id,

            u.user_id,
            u.archived_at,
            u.email as user_email_ws,
            u.name as user_name_ws,
            u.default_information_school as school_id_ws,
            u.default_information_grade_level as grade_id_ws,
            u.default_information_course as course_id_ws,
            u.coach as coach_id_ws,

            um.user_id as coach_id,

            sch.school_id,

            cou.tag_id as course_id,

            gr.tag_id as grade_id,

            u.roles[0]._id as role_id_ws,

            if(u.inactive, 1, 0) as inactive_ws,

            case
                when p.role_name = 'Coach'
                then 'observees;observers'
                when p.role_name like '%Admin%'
                then 'observers'
                else 'observees'
            end as group_type,
        from people as p
        inner join {{ ref("stg_schoolmint_grow__roles") }} as r on p.role_name = r.name
        left join
            {{ ref("stg_schoolmint_grow__users") }} as u
            on p.user_internal_id = u.internal_id_int
        left join
            {{ ref("stg_schoolmint_grow__users") }} as um
            on p.manager_internal_id = um.internal_id_int
        left join
            {{ ref("stg_schoolmint_grow__schools") }} as sch on p.school_name = sch.name
        left join
            {{ ref("stg_schoolmint_grow__generic_tags") }} as cou
            on p.course_name = cou.name
            and cou.tag_type = 'courses'
        left join
            {{ ref("stg_schoolmint_grow__generic_tags") }} as gr
            on p.grade_abbreviation = gr.abbreviation
            and gr.tag_type = 'grades'
    ),

    surrogate_keys as (
        select
            *,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "coach_id",
                        "course_id",
                        "grade_id",
                        "inactive",
                        "role_id",
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
                        "role_id_ws",
                        "school_id_ws",
                        "user_email_ws",
                        "user_name_ws",
                    ]
                )
            }} as surrogate_key_destination,
        from roster
    )

select *,
from surrogate_keys
where
    /* create */
    (inactive = 0 and user_id is null)
    /* archive */
    or (inactive = 1 and user_id is not null and archived_at is null)
    /* update/reactivate */
    or inactive = 0
