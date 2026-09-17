with
    gpa_cumulative as (
        select
            studentid,
            schoolid,
            dbt_valid_from,
            dbt_valid_to,
            cumulative_y1_gpa_projected_unweighted,

            /* snapshot-fed: derive locally — the check strategy never backfills
               the stored column across history (see kipptaf CLAUDE.md) */
            {{ extract_source_project() }} as _dbt_source_project,
        from {{ ref("snapshot_powerschool__gpa_cumulative") }}
        where
            /* TODO(#4318): drop once dev-relation ghost rows are purged — the
               prod snapshot holds zz_cbini_* rows whose region regex matches
               the join below, so they fan a student-week out a second time */
            regexp_contains(_dbt_source_relation, r'\.`kipp[a-z]+_powerschool`\.')
    ),

    enrollment_weeks as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,
            studentid,
            schoolid,
            _dbt_source_project,

            /* first instant of the day AFTER the week closes, local — i.e. the
               value in effect at the END of the week */
            timestamp(
                date_add(week_end_sunday, interval 1 day), '{{ var("local_timezone") }}'
            ) as week_end_boundary,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            is_enrolled_week
            and school_level in ('MS', 'HS')
            and academic_year >= {{ var("current_academic_year") - 1 }}
    )

select
    co.student_number,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,

    gpa.cumulative_y1_gpa_projected_unweighted,
from enrollment_weeks as co
left join
    gpa_cumulative as gpa
    on co.studentid = gpa.studentid
    and co.schoolid = gpa.schoolid
    and co._dbt_source_project = gpa._dbt_source_project
    and co.week_end_boundary > gpa.dbt_valid_from
    and co.week_end_boundary <= gpa.dbt_valid_to
