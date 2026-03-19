/*
  Fall 2025 Enrollment Analysis
  Counselors: Evetha, Jared
  Source: rpt_tableau__kfwd_persistence

  Metrics per dataset (All Alum | KIPP HS Grads):
    - Fall 2025 N: distinct students enrolled at Oct 31 persistence checkpoint
    - Withdrew: enrollment ended Aug–Dec 2025, not via graduation
    - Graduated: enrollment ended Aug–Dec 2025 with Graduated status
    - Spring 2026 Attending: active enrollment spanning into Spring 2026 (as of 2026-03-19)
    - Other: Fall 2025 N minus the three buckets above (for 100% stacked bars)
*/

with
    base as (
        select *
        from {{ ref("rpt_tableau__kfwd_persistence") }}
        where
            lower(counselor_name) like '%evetha%'
            or lower(counselor_name) like '%jared%'
    ),

    fall_2025 as (
        select distinct student_number, is_kipp_hs_graduate,
        from base
        where semester = 'Fall' and academic_year = 2025
    ),

    withdrew_fall_2025 as (
        select distinct student_number
        from base
        where
            semester = 'Fall'
            and academic_year = 2025
            and actual_end_date between '2025-08-01' and '2025-12-31'
            and lower(coalesce(enrollment_status, '')) != 'graduated'
    ),

    graduated_fall_2025 as (
        select distinct student_number
        from base
        where
            semester = 'Fall'
            and academic_year = 2025
            and enrollment_status = 'Graduated'
            and actual_end_date between '2025-08-01' and '2025-12-31'
    ),

    /*
      Spring 2026: Mar 31 persistence checkpoint has not yet occurred (today
      is 2026-03-19), so use a date-based enrollment filter instead of
      semester = 'Spring'. Restricts to Fall 2025 cohort via INNER JOIN.
    */
    spring_2026 as (
        select distinct p.student_number
        from {{ ref("rpt_tableau__kfwd_persistence") }} as p
        inner join fall_2025 as f on p.student_number = f.student_number
        where
            p.start_date <= '2026-03-19'
            and (p.actual_end_date is null or p.actual_end_date >= '2026-01-01')
            and p.enrollment_status = 'Attending'
    ),

    summary as (
        select
            'All Alum' as dataset,
            count(distinct f.student_number) as fall_2025_n,
            count(distinct w.student_number) as withdrew_n,
            count(distinct g.student_number) as graduated_n,
            count(distinct s.student_number) as spring_2026_n,
        from fall_2025 as f
        left join withdrew_fall_2025 as w on f.student_number = w.student_number
        left join graduated_fall_2025 as g on f.student_number = g.student_number
        left join spring_2026 as s on f.student_number = s.student_number

        union all

        select
            'KIPP HS Grads' as dataset,
            count(distinct f.student_number) as fall_2025_n,
            count(distinct w.student_number) as withdrew_n,
            count(distinct g.student_number) as graduated_n,
            count(distinct s.student_number) as spring_2026_n,
        from fall_2025 as f
        left join withdrew_fall_2025 as w on f.student_number = w.student_number
        left join graduated_fall_2025 as g on f.student_number = g.student_number
        left join spring_2026 as s on f.student_number = s.student_number
        where f.is_kipp_hs_graduate = true
    )

select
    dataset,
    fall_2025_n,
    withdrew_n,
    round(100.0 * withdrew_n / nullif(fall_2025_n, 0), 1) as withdrew_pct,
    graduated_n,
    round(100.0 * graduated_n / nullif(fall_2025_n, 0), 1) as graduated_pct,
    spring_2026_n,
    round(100.0 * spring_2026_n / nullif(fall_2025_n, 0), 1) as spring_2026_pct,
    fall_2025_n - withdrew_n - graduated_n - spring_2026_n as other_n,
    round(
        100.0
        * (fall_2025_n - withdrew_n - graduated_n - spring_2026_n)
        / nullif(fall_2025_n, 0),
        1
    ) as other_pct,
from summary
order by dataset
