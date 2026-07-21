select g.schoolid, g.grade_level, g.region as sheet_region, s.region as scaffold_region,

from {{ ref("stg_google_sheets__finalsite__goals") }} as g
inner join
    {{ ref("int_finalsite__enrollment_scaffold") }} as s
    on g.schoolid = s.schoolid
    and g.grade_level = s.grade_level
    and g.enrollment_academic_year = s.academic_year
where g.region != s.region and g.schoolid != 0
