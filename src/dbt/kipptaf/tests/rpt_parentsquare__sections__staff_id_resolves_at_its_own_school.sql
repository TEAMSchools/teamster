-- A section's owner must hold a staff row at that section's OWN school, not
-- merely somewhere in staff.csv. The relationships test on sections.staff_id is
-- single-column, so it passes as long as the employee number appears anywhere in
-- the staff feed — and these views span every NJ region, so an owner drawn from
-- another region would satisfy it while dangling in this region's file.
-- rpt_parentsquare__staff fans each Operations leader across the schools of their
-- own region only, so (school_id, staff_id) is the pair that has to resolve. The
-- Clever feeds shipped exactly this class of cross-region leak before — see
-- rpt_clever__school_id_resolves_to_schools_feed.
--
-- Null owners are excluded: that is the not_null test's job on
-- rpt_parentsquare__sections.staff_id, and reporting them here would double-count
-- the same failure.
select s.school_id, s.section_id, s.staff_id,
from {{ ref("rpt_parentsquare__sections") }} as s
left join
    {{ ref("rpt_parentsquare__staff") }} as f
    on s.school_id = f.school_id
    and s.staff_id = f.staff_id
where s.staff_id is not null and f.staff_id is null
