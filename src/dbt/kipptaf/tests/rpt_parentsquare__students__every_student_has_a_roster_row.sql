select s.student_id,
from {{ ref("rpt_parentsquare__students") }} as s
left join {{ ref("rpt_parentsquare__rosters") }} as r on s.student_id = r.student_id
where r.student_id is null
