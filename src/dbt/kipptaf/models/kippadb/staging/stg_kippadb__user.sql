select id, name, email, phone, from {{ source("kippadb", "user") }}
