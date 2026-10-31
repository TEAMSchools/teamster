-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause A = dashboard: the dashboard keeps only days with membershipvalue = 1
-- cause B = dashboard: the dashboard drops days whose attendancevalue is null
-- cause C = dashboard: the dashboard codes out-of-district students school_level OD, not HS
-- reproduce C:
--  SELECT school_abbreviation, COUNT(*) AS n_days
--  FROM `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__attendance_dashboard`
--  WHERE academic_year = 2026 AND school_level = 'OD' AND grade_level >= 9
--  GROUP BY school_abbreviation

WITH ad AS (
  SELECT
    CAST(student_number AS STRING) AS sn,
    calendardate,
    LOGICAL_OR(membershipvalue = 1) AS has_membership,
    LOGICAL_OR(membershipvalue = 1 AND attendancevalue IS NOT NULL) AS has_attendance
  FROM `teamster-332318`.`kipptaf_students`.`int_students__attendance_daily`
  GROUP BY sn, calendardate
),

d AS (
  SELECT
    CAST(student_number AS STRING) AS sn,
    calendardate,
    LOGICAL_OR(school_level = 'OD') AS is_od
  FROM `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__attendance_dashboard`
  GROUP BY sn, calendardate
)

SELECT
  u.__row,
  CASE
    WHEN ad.sn IS NULL THEN 'UNEXPLAINED'
    WHEN NOT ad.has_membership THEN 'A'
    WHEN NOT ad.has_attendance THEN 'B'
    WHEN d.is_od THEN 'C'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u
LEFT JOIN ad
  ON ad.sn = CAST(u.lea_student_identifier AS STRING)
  AND ad.calendardate = CAST(u.attendance_date AS DATE)
LEFT JOIN d
  ON d.sn = CAST(u.lea_student_identifier AS STRING)
  AND d.calendardate = CAST(u.attendance_date AS DATE)
