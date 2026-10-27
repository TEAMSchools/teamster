select
    `student_school_enrollments`.grade_level `student_attendance_enrollment_daily_view__grade_level`,
    `locations`.abbreviation `student_attendance_enrollment_daily_view__locations_abbreviation`,
    sum(
        case
            when (`student_attendance_enrollment_daily`.membership_value = 1)
            then `student_attendance_enrollment_daily`.attendance_value
        end
    ) / nullif(
        sum(
            case
                when
                    (`student_attendance_enrollment_daily`.membership_value = 1)
                    and (
                        `student_attendance_enrollment_daily`.attendance_value
                        is not null
                    )
                then `student_attendance_enrollment_daily`.membership_value
            end
        ),
        0
    ) `student_attendance_enrollment_daily_view__avg_daily_attendance`,
    count(
        distinct `student_school_enrollments`.student_key
    ) `student_attendance_enrollment_daily_view__count_students`
from
    kipptaf_marts.fct_student_attendance_enrollment_daily
    as `student_attendance_enrollment_daily`
left join
    kipptaf_marts.dim_student_enrollments as `student_school_enrollments`
    on `student_school_enrollments`.student_enrollment_key
    = `student_attendance_enrollment_daily`.student_enrollment_key

left join
    kipptaf_marts.dim_locations as `locations`
    on `locations`.location_key = `student_school_enrollments`.location_key
left join
    kipptaf_marts.dim_dates as `dates`
    on `dates`.date_key = `student_attendance_enrollment_daily`.date_key
left join
    kipptaf_marts.dim_regions as `regions`
    on `regions`.region_key = `locations`.region_key
where
    (`dates`.academic_year = cast(? as float64))
    and (`regions`.`name` = ?)
    and (`locations`.abbreviation in (?, ?, ?))
group by 1, 2
order by 3 desc
limit 50000
