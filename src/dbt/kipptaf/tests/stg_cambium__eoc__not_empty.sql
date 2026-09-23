select count(*) as records, from {{ ref("stg_cambium__eoc") }} having count(*) = 0
