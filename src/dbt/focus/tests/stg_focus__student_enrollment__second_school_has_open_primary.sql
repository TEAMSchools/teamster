-- Any returned row is a second-school enrollment with no primary enrollment
-- open on its start date. Rationale in tests/properties.yml.
select f.student_id, f.syear, f.start_date,
from {{ ref("stg_focus__student_enrollment") }} as f
left join
    {{ ref("stg_focus__student_enrollment") }} as p
    on f.student_id = p.student_id
    and f.syear = p.syear
    and f.start_date >= p.start_date
    and (f.start_date <= p.end_date or p.end_date is null)
    and p.second_school is null
where f.second_school is not null and p.id is null
