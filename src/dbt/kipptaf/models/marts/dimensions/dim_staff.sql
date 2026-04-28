with
    employee_numbers as (
        select employee_number,
        from {{ ref("stg_people__employee_numbers") }}
        where adp_associate_id is not null and is_active
    ),

    staff_history as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_people__staff_roster_history"),
                partition_by="employee_number",
                order_by="primary_indicator desc, effective_date_start desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["en.employee_number"]) }} as staff_key,

    en.employee_number as staff_unique_id,

    sh.formatted_name as full_name,
    sh.given_name as first_name,
    sh.family_name_1 as last_name,

    sh.birth_date,

    sh.gender_identity,
    sh.race_ethnicity_reporting as race,
    sh.is_hispanic,

    sh.work_email,
    sh.personal_email,
    sh.personal_cell as personal_cell_phone,

    sh.sam_account_name as active_directory_username,
    sh.google_email,

    sh.worker_original_hire_date as original_hire_date,
    sh.worker_rehire_date as rehire_date,
from employee_numbers as en
left join staff_history as sh on en.employee_number = sh.employee_number
