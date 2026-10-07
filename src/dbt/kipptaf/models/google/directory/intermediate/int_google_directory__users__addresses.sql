select primary_email, addr.address,
from {{ ref("stg_google_directory__users") }}, unnest(emails) as addr

union distinct

select primary_email, alias as address,
from {{ ref("stg_google_directory__users") }}, unnest(aliases) as alias

union distinct

select primary_email, primary_email as address,
from {{ ref("stg_google_directory__users") }}
