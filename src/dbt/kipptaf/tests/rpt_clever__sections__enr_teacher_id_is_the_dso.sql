-- The auto-generated ENR sections carry the school's DSO as their primary
-- teacher and the School Leader as the backup. Both match the same job-title
-- filter, so the pick is only stable because `sortorder` ranks them; drop that
-- rank and the two swap on scan order, silently and without failing anything.
-- Clever names each section after its primary teacher, so a swap rewrites every
-- ENR section name and trips its churn alert. A teacher_id that resolves to no
-- active roster row at all lands here too.
select s.section_id, s.teacher_id, sr.job_title,
from {{ ref("rpt_clever__sections") }} as s
left join
    {{ ref("int_people__staff_roster") }} as sr
    on s.teacher_id = sr.powerschool_teacher_number
    and sr.assignment_status != 'Terminated'
where
    s.course_number = 'ENR'
    and coalesce(sr.job_title, 'unresolved') not in (
        'Director of Campus Operations',
        'Director Campus Operations',
        'Director School Operations'
    )
