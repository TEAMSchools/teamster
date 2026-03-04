select
    df_employee_number as employee_number,
    salesforce_id,
    adp_associate_id as adp_associate_id_archive,
    first_name as legal_first_name,
    last_name as legal_last_name,
    ethnicity,
    gender,
    mobile_number,
    `address`,
    city,
    `state`,
    grades_taught,
    subjects_taught,

    cast(employee_s_manager_s_df_emp_number_id as int) as manager_employee_number,
    cast(birth_date as date) as birth_date,
    cast(original_hire_date as date) as original_hire_date,
    cast(rehire_date as date) as rehire_date,
    cast(termination_date as date) as termination_date,
    cast(position_effective_from_date as date) as position_effective_from_date,
    cast(position_effective_to_date as date) as position_effective_to_date,

    coalesce(common_name, first_name) as preferred_first_name,
    coalesce(preferred_last_name, last_name) as preferred_last_name,

    right(concat('0', cast(postal_code as int)), 5) as postal_code,
from {{ source("dayforce", "src_dayforce__employees") }}
