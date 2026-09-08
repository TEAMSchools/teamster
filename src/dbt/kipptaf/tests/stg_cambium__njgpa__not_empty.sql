select count(*) as records, from {{ ref("stg_cambium__njgpa") }} having count(*) = 0
