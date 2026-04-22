with
    employee_numbers as (
        select employee_number, adp_associate_id,
        from {{ ref("stg_people__employee_numbers") }}
        where is_active
    ),

    employee_memberships as (
        select
            associate_id,
            membership_code,
            membership_description,
            category_code,
            category_description,
            effective_date,
            expiration_date,
        from {{ ref("stg_adp_workforce_now__employee_memberships") }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "en.employee_number",
                "em.membership_code",
                "em.effective_date",
            ]
        )
    }} as staff_membership_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["en.employee_number"]) }} as staff_key,

    em.membership_code,
    em.membership_description,
    em.category_code,
    em.category_description,

    em.effective_date as effective_start_date,
    em.expiration_date as effective_end_date,
from employee_memberships as em
inner join employee_numbers as en on em.associate_id = en.adp_associate_id
