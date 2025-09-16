with
    date_spine as (
        select
            membership_effective_date,
            {{
                date_to_fiscal_year(
                    date_field="membership_effective_date",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from
            unnest(
                generate_date_array(
                    /* first date of the membership snapshot*/
                    '2003-04-01',
                    date_add(
                        current_date('{{ var("local_timezone") }}'), interval 1 year
                    ),
                    interval 1 year
                )
            ) as membership_effective_date
    ),
    by_academic_year as (
        select
            em.associate_id,
            em.membership_description,
            em.is_leader_development_program,
            em.is_teacher_development_program,
            d.academic_year,
        from {{ ref("stg_adp_workforce_now__employee_memberships") }} as em
        left join
            date_spine as d
            on d.membership_effective_date
            between em.effective_date and em.expiration_date
        left join
            {{ ref("int_people__staff_roster") }} as sr
            on em.associate_id = sr.worker_id
            and sr.worker_termination_date
            between em.effective_date and em.expiration_date
        where em.membership_code is not null
    )

select
    associate_id,
    academic_year,
    max(is_leader_development_program) as is_leader_development_program,
    max(is_teacher_development_program) as is_teacher_development_program,
    string_agg(membership_description, ', ') as memberships
from by_academic_year
group by associate_id, academic_year
