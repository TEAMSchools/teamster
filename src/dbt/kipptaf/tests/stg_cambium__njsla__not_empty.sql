select count(*) as records, from {{ ref("stg_cambium__njsla") }} having count(*) = 0
