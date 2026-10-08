select count(*) as records,
from {{ ref("stg_cambium__njsla") }}
where `subject` in ('Algebra I', 'Algebra II', 'Geometry')
having count(*) = 0
