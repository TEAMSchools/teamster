with
    date_spine as (
        select
            ay_start_date,
            date_add(
                date_add(ay_start_date, interval -3 day), interval 1 year
            ) as ay_end_date,
            {{
                date_to_fiscal_year(
                    date_field="ay_start_date",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from
            unnest(
                generate_date_array(
                    /* first date of the membership snapshot*/
                    '2002-07-02',
                    date_add(
                        current_date('{{ var("local_timezone") }}'), interval 1 year
                    ),
                    interval 1 year
                )
            ) as ay_start_date
    ),

    by_academic_year as (
        select
            em.associate_id,
            em.membership_description,
            em.is_leader_development_program,
            em.is_teacher_development_program,
            d.academic_year,
        from {{ ref("stg_adp_workforce_now__employee_memberships") }} as em
        inner join
            date_spine as d
            on (d.ay_start_date between em.effective_date and em.expiration_date)
            or (d.ay_end_date between em.effective_date and em.expiration_date)
            or (em.effective_date between d.ay_start_date and d.ay_end_date)
            or (em.expiration_date between d.ay_start_date and d.ay_end_date)
    )

select
    associate_id,
    academic_year,
    max(is_leader_development_program) as is_leader_development_program,
    max(is_teacher_development_program) as is_teacher_development_program,
    string_agg(membership_description, ', ') as memberships,
from by_academic_year
group by associate_id, academic_year
