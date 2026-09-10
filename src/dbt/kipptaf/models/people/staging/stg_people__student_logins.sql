{% if env_var("DBT_CLOUD_ENVIRONMENT_TYPE", "") in ["dev", "staging"] %}
    select student_number, username, default_password, google_email,
    from {{ source("people", "src_people__student_logins") }}
{% elif is_incremental() %}
    with
        existing_logins as (select student_number, username, from {{ this }}),

        miami_candidates as (
            select
                c.first_name,
                c.last_name,
                c.birth_date,

                cast(ida.focus_student_id_prefixed as int64) as student_number,
                cast(ida.focus_student_id as int64) as student_number_bare,
            from {{ ref("stg_finalsite__contacts") }} as c
            inner join
                {{ ref("int_finalsite__contact_id_attributes") }} as ida
                on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
                and ida.focus_student_id_prefixed is not null
            where c.status = 'enrolled'
        ),

        union_source as (
            select
                student_number,
                dob,
                first_name,
                last_name,

                cast(null as int64) as student_number_bare,
            from {{ ref("stg_powerschool__students") }}
            where
                _dbt_source_project != 'kippmiami'
                and dob is not null
                and first_name is not null
                and last_name is not null
                and enroll_status = 0

            union all

            select
                student_number,
                birth_date as dob,
                first_name,
                last_name,
                student_number_bare,
            from miami_candidates
            where
                birth_date is not null
                and first_name is not null
                and last_name is not null
        ),

        new_students as (
            select u.student_number, u.dob, u.first_name, u.last_name,
            from union_source as u
            left join existing_logins as e1 on u.student_number = e1.student_number
            left join existing_logins as e2 on u.student_number_bare = e2.student_number
            where e1.student_number is null and e2.student_number is null
        ),

        components as (
            select
                student_number,

                format_date('%m', dob) as dob_month,
                format_date('%d', dob) as dob_day,
                format_date('%y', dob) as dob_year,

                regexp_replace(
                    normalize(lower(first_name), nfd), r'[\pM\W]', ''
                ) as first_name_clean,

                regexp_replace(
                    normalize(
                        lower(regexp_replace(last_name, r'\s[IiVvXxJjRr\.]*$', '')), nfd
                    ),
                    r'[\pM\W]',
                    ''
                ) as last_name_clean,
            from new_students
        ),

        username_candidates as (
            /* powerschool usernames are capped @ 20 chars  */
            select
                student_number,
                last_name_clean,
                dob_year,

                concat(left(last_name_clean, 12), dob_month, dob_day) as username_1,
                concat(left(first_name_clean, 12), dob_month, dob_day) as username_2,

                concat(
                    left(concat(left(first_name_clean, 1), last_name_clean), 12),
                    dob_month,
                    dob_day
                ) as username_3,

                concat(
                    left(concat(first_name_clean, left(last_name_clean, 1)), 12),
                    dob_month,
                    dob_day
                ) as username_4,

                concat(
                    left(concat(first_name_clean, last_name_clean), 10),
                    dob_month,
                    dob_day,
                    dob_year
                ) as username_5,
            from components
        ),

        username_options as (
            select c.student_number, o.priority_order, o.username,
            from username_candidates as c
            cross join
                unnest(
                    array<struct<priority_order int64, username string>>[
                        (1, c.username_1),
                        (2, c.username_2),
                        (3, c.username_3),
                        (4, c.username_4),
                        (5, c.username_5)
                    ]
                ) as o
        ),

        username_filter as (
            select
                o.student_number,
                o.priority_order,
                o.username,

                row_number() over (
                    partition by o.username
                    order by o.priority_order asc, o.student_number asc
                ) as rn_username,
            from username_options as o
            left join existing_logins as e on o.username = e.username
            where e.username is null
        ),

        username_pick as (
            select
                student_number,

                coalesce(
                    max(if(priority_order = 1 and rn_username = 1, username, null)),
                    max(if(priority_order = 2 and rn_username = 1, username, null)),
                    max(if(priority_order = 3 and rn_username = 1, username, null)),
                    max(if(priority_order = 4 and rn_username = 1, username, null)),
                    max(if(priority_order = 5 and rn_username = 1, username, null))
                ) as username,
            from username_filter
            group by student_number
        ),

        username_password as (
            select
                c.student_number,

                p.username,

                if(
                    length(concat(c.last_name_clean, c.dob_year)) < 8,
                    left(concat(c.last_name_clean, c.dob_year, c.student_number), 8),
                    concat(left(c.last_name_clean, 18), c.dob_year)  /* 20 char limit */
                ) as default_password,
            from username_candidates as c
            inner join username_pick as p on c.student_number = p.student_number
        )

    select *, username || '@teamstudents.org' as google_email,
    from username_password
    where username is not null
{% else %}
    select student_number, username, default_password, google_email,
    from
        {{
            source(
                "google_sheets",
                "stg_google_sheets__people__student_logins_archive",
            )
        }}
{% endif %}

    -- depends_on: {{ ref("stg_powerschool__students") }}
    -- depends_on: {{ ref("stg_finalsite__contacts") }}
    -- depends_on: {{ ref("int_finalsite__contact_id_attributes") }}
    -- trunk-ignore(sqlfluff/LT05)
    -- depends_on: {{ source("google_sheets", "stg_google_sheets__people__student_logins_archive") }}
    -- depends_on: {{ source("people", "src_people__student_logins") }}
