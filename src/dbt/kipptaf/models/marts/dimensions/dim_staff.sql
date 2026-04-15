with
    staff as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_people__staff_roster_history"),
                partition_by="employee_number",
                order_by="primary_indicator desc, effective_date_start desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    employee_number,

    formatted_name,
    given_name,
    family_name_1,

    birth_date,

    gender_identity,
    race_ethnicity_reporting,
    is_hispanic,

    work_email,
    personal_email,
    personal_cell,

    sam_account_name,
    google_email,

    worker_original_hire_date as original_hire_date,
    worker_rehire_date as rehire_date,
from staff
