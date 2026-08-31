with
    staff as (
        select
            *,

            /*
                job_function is the only tier input. A null job_function is an
                ADP data defect and is deliberately not patched over here --
                see docs/superpowers/specs/2026-08-28-grow-region-scoped-admin-design.md
            */
            coalesce(
                job_function in ('Teacher', 'Teacher in Residence'), false
            ) as is_teacher,

            /*
                ADP records some Associate Directors at staff level, which
                understates them. This is the one deliberate title exception.
            */
            if(
                job_function = 'KTAF or Regional Staff'
                and contains_substr(job_title, 'Associate Director'),
                'KTAF or Regional Director',
                job_function
            ) as tier,

            home_department_name in (
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
        from {{ ref("int_people__staff_roster") }}
        where home_work_location_dagster_code_location != 'kipppaterson'
    ),

    grow_schools as (
        select sch.school_id, lc.location_dagster_code_location as region,
        from {{ ref("stg_schoolmint_grow__schools") }} as sch
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on sch.name = lc.location_name
        where sch.archived_at is null
    ),

    instructional_managers as (
        select distinct sr.reports_to_employee_number,
        from staff as sr
        join staff as srm on sr.reports_to_employee_number = srm.employee_number
        where
            sr.assignment_status in ('Active', 'Leave')
            and (
                sr.is_teacher
                or srm.home_department_name
                in ('School Support', 'Student Support', 'KIPP Forward')
            )
    ),

    people as (
        select
            sr.employee_number as user_internal_id,
            sr.google_email as user_email,
            sr.reports_to_employee_number as manager_internal_id,
            sr.home_work_location_reporting_name as school_name,
            sr.home_department_name as course_name,
            sr.tier,
            sr.home_work_location_dagster_code_location as region,

            sr.given_name || ' ' || sr.family_name_1 as user_name,

            if(sr.assignment_status in ('Terminated', 'Deceased'), 1, 0) as inactive,

            if(
                sr.primary_grade_level_taught = 0,
                'K',
                cast(sr.primary_grade_level_taught as string)
            ) as grade_abbreviation,

            /*
                Every predicate is independent and contributes at most one role.
                Nothing suppresses anything else, which is what lets an admin
                who manages teachers keep Coach.

                Chief Level and the three Director tiers both resolve to
                Regional Admin here; they differ only in school scope, which
                sub-project 2 supplies.
            */
            array(
                select rn
                from
                    unnest(
                        [
                            case
                                when
                                    sr.tier in (
                                        'Chief Level',
                                        'EDs, HOSs, MDOs',
                                        'KTAF or Regional Managing Director',
                                        'KTAF or Regional Director'
                                    )
                                    and sr.passes_department_gate
                                then 'Regional Admin'
                                when sr.tier = 'School Leader'
                                then 'School Admin'
                                when sr.tier in ('Assistant School Leaders', 'Deans')
                                then 'School Assistant Admin'
                            end,
                            if(
                                sr.employee_number in (
                                    select reports_to_employee_number
                                    from instructional_managers
                                ),
                                'Coach',
                                null
                            ),
                            if(sr.is_teacher, 'Teacher', null)
                        ]
                    ) as rn
                where rn is not null
            ) as role_names,
        from staff as sr
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
            ifnull(array_agg(rn ignore nulls order by r.role_id), []) as role_names,
            ifnull(
                array_agg(r.role_id ignore nulls order by r.role_id), []
            ) as role_ids,
        from people as p
        left join unnest(p.role_names) as rn
        left join {{ ref("stg_schoolmint_grow__roles") }} as r on rn = r.name
        group by p.user_internal_id
    ),

    regional_scope as (
        select
            p.user_internal_id,
            array_agg(gs.school_id order by gs.school_id) as school_ids,
        from people as p
        inner join
            grow_schools as gs on (p.tier = 'Chief Level' or gs.region = p.region)
        where 'Regional Admin' in unnest(p.role_names)
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

            /*
                Chief Level sees every active school; the other Regional
                Admin tiers see their own region. Everyone else gets an
                empty array. [Training School] has no crosswalk region, so
                it appears only in the all-schools case.
            */
            ifnull(rs.school_ids, []) as regional_admin_school_ids,

            if('Regional Admin' in unnest(pra.role_names), 1, 0) as readonly,

            array(
                select s._id from unnest(u.regional_admin_schools) as s order by s._id
            ) as regional_admin_school_ids_ws,

            if(u.read_only, 1, 0) as readonly_ws,

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

            /*
                Observee and observer are independent. An admin who coaches is
                both; Regional Admin is an observer only, because a regional
                leader is not observed inside a school's Teachers group.
            */
            case
                when
                    exists (
                        select 1
                        from unnest(pra.role_names) as rn
                        where
                            rn in ('Teacher', 'School Admin', 'School Assistant Admin')
                    )
                    and exists (
                        select 1
                        from unnest(pra.role_names) as rn
                        where
                            rn in (
                                'Regional Admin',
                                'School Admin',
                                'School Assistant Admin',
                                'Coach'
                            )
                    )
                then 'observees;observers'
                when
                    exists (
                        select 1
                        from unnest(pra.role_names) as rn
                        where
                            rn in (
                                'Regional Admin',
                                'School Admin',
                                'School Assistant Admin',
                                'Coach'
                            )
                    )
                then 'observers'
                when
                    exists (
                        select 1
                        from unnest(pra.role_names) as rn
                        where
                            rn in ('Teacher', 'School Admin', 'School Assistant Admin')
                    )
                then 'observees'
                else ''
            end as group_type,
        from people as p
        inner join people_roles as pra on p.user_internal_id = pra.user_internal_id
        inner join
            {{ ref("stg_schoolmint_grow__schools") }} as sch on p.school_name = sch.name
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
    surrogate_key_source,
    surrogate_key_destination,
from surrogate_keys
where
    /*
        Only emit a row the sync can act on. A user with no roles and no Grow
        account has nothing to create, update, or archive -- emitting them
        would make the create branch open an empty account.
    */
    (array_length(role_ids) > 0 or user_id is not null)
    and (
        /* create, update, or reactivate */
        inactive = 0
        /* archive */
        or (inactive = 1 and user_id is not null and archived_at is null)
    )
