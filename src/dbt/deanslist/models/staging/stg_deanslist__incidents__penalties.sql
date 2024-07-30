select
    i.incident_id,

    p.isreportable as is_reportable,
    p.issuspension as is_suspension,
    p.print as `print`,

    nullif(p.penaltyname, '') as penalty_name,

    safe_cast(nullif(p.incidentpenaltyid, '') as int) as incident_penalty_id,
    safe_cast(nullif(p.penaltyid, '') as int) as penalty_id,
    safe_cast(nullif(p.said, '') as int) as said,
    safe_cast(nullif(p.schoolid, '') as int) as school_id,
    safe_cast(nullif(p.studentid, '') as int) as student_id,
    safe_cast(nullif(p.numperiods, '') as int) as num_periods,
    safe_cast(nullif(p.startdate, '') as date) as `start_date`,
    safe_cast(nullif(p.enddate, '') as date) as end_date,

    coalesce(
        p.numdays.double_value, safe_cast(p.numdays.long_value as numeric)
    ) as num_days,
from {{ ref("stg_deanslist__incidents") }} as i
cross join unnest(i.penalties) as p
