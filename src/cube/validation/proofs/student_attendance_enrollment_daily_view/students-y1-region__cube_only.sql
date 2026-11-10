-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C1 = dashboard: the dashboard keeps only membership days with a recorded attendance value

with
    member_days as (
        select
            ad.student_number,
            ad.calendardate,
            ad._dbt_source_project,
            logical_or(ad.attendancevalue is not null) as has_recorded_attendance,
        from `teamster-332318`.`kipptaf_students`.`int_students__attendance_daily` as ad
        where ad.membershipvalue = 1
        group by ad.student_number, ad.calendardate, ad._dbt_source_project
    )

select
    u.__row,
    case
        when md.calendardate is null then 'UNEXPLAINED'
        when not md.has_recorded_attendance then 'C1'
        else 'UNEXPLAINED'
    end as cause,
from {unmatched} as u
left join
    `teamster-332318`.`kipptaf_marts`.`dim_regions` as r
    on u.regions_region_name = r.name
left join
    member_days as md
    on cast(u.lea_student_identifier as string) = cast(md.student_number as string)
    and cast(u.attendance_date as date) = md.calendardate
    and r.dagster_code_location = md._dbt_source_project
