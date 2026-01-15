with
    date_spine as (
        select
            date_day,

            {{
                date_to_fiscal_year(
                    date_field="date_day", start_month=7, year_source="start"
                )
            }} as academic_year,
        from
            unnest(
                generate_date_array(
                    '2002-07-01',  -- first date of the membership snapshot
                    date_add(
                        current_date('{{ var("local_timezone") }}'), interval 1 year
                    ),
                    interval 1 day
                )
            ) as date_day
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
            on d.date_day between em.effective_date and em.expiration_date
    )

select
    associate_id,
    academic_year,

    max(is_leader_development_program) as is_leader_development_program,
    max(is_teacher_development_program) as is_teacher_development_program,

    string_agg(distinct membership_description, ', ') as memberships,
from by_academic_year
group by associate_id, academic_year
