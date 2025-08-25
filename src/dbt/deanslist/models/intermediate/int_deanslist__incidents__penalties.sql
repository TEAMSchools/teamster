with
    incidents_penalties as (
        select
            i.* except (actions, attachments, custom_fields, penalties),

            p.isreportable as is_reportable,
            p.issuspension as is_suspension,
            p.print as `print`,

            cast(nullif(p.incidentpenaltyid, '') as int) as incident_penalty_id,
            cast(nullif(p.penaltyid, '') as int) as penalty_id,
            cast(nullif(p.schoolid, '') as int) as penalty_school_id,
            cast(nullif(p.studentid, '') as int) as penalty_student_id,
            cast(nullif(p.said, '') as int) as said,

            cast(nullif(p.numperiods, '') as numeric) as num_periods,

            cast(nullif(p.startdate, '') as date) as `start_date`,
            cast(nullif(p.enddate, '') as date) as end_date,

            nullif(p.penaltyname, '') as penalty_name,

            coalesce(
                p.numdays.double_value, cast(p.numdays.long_value as numeric)
            ) as num_days,
        from {{ ref("int_deanslist__incidents") }} as i
        left join unnest(i.penalties) as p
    )

select
    *,

    case
        when
            penalty_name in (
                'Out of School Suspension',
                'KM: Out-of-School Suspension',
                'KNJ: Out-of-School Suspension'
            )
        then 'OSS'
        when
            penalty_name in (
                'In School Suspension',
                'KM: In-School Suspension',
                'KNJ: In-School Suspension'
            )
        then 'ISS'
    end as suspension_type,
from incidents_penalties
