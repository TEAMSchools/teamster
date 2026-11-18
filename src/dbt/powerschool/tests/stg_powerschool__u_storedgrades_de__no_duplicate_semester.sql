-- depends_on: {{ ref("stg_powerschool__u_storedgrades_de") }}
-- Rationale lives in this test's tests/properties.yml description.
-- Any returned row is a failure.
select
    storedgradesdcid, de_semester, count(*) as n_rows, array_agg(id order by id) as ids,
from {{ source("powerschool_dlt", "u_storedgrades_de") }}
group by storedgradesdcid, de_semester
having count(*) > 1
