-- depends_on: {{ ref("stg_ldap__user_person") }}
select employeenumber, count(*) as n_accounts,
from {{ source("ldap", "src_ldap__user_person") }}
where employeenumber is not null
group by employeenumber
having count(*) > 1
