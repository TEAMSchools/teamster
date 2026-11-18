-- depends_on: {{ ref("stg_ldap__user_person") }}
-- same cast as the model, so blank or non-numeric values do not count
with
    accounts as (
        select safe_cast(employeenumber as int) as employee_number,
        from {{ source("ldap", "src_ldap__user_person") }}
    )

select employee_number, count(*) as n_accounts,
from accounts
where employee_number is not null
group by employee_number
having count(*) > 1
