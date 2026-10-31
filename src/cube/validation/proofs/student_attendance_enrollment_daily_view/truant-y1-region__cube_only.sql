-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause A = dashboard: the dashboard keeps only days with membershipvalue = 1
-- cause B = dashboard: the dashboard drops days whose attendancevalue is null
-- reproduce A:
--  SELECT co.region, COUNT(*) AS n_days
--  FROM `teamster-332318`.`kipptaf_students`.`int_students__attendance_daily` AS ad
--  INNER JOIN `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments` AS co
--    ON ad.student_number = co.student_number AND ad.schoolid = co.schoolid
--    AND ad.calendardate BETWEEN co.entrydate AND co.exitdate
--    AND ad._dbt_source_project = co._dbt_source_project
--  WHERE co.academic_year = 2026 AND ad.membershipvalue != 1
--  GROUP BY co.region
-- reproduce B:
--  SELECT co.region, COUNT(*) AS n_days
--  FROM `teamster-332318`.`kipptaf_students`.`int_students__attendance_daily` AS ad
--  INNER JOIN `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments` AS co
--    ON ad.student_number = co.student_number AND ad.schoolid = co.schoolid
--    AND ad.calendardate BETWEEN co.entrydate AND co.exitdate
--    AND ad._dbt_source_project = co._dbt_source_project
--  WHERE co.academic_year = 2026 AND ad.membershipvalue = 1
--    AND ad.attendancevalue IS NULL
--  GROUP BY co.region

WITH ad AS (
  SELECT
    CAST(student_number AS STRING) AS sn,
    calendardate,
    LOGICAL_OR(membershipvalue = 1) AS has_membership,
    LOGICAL_OR(membershipvalue = 1 AND attendancevalue IS NOT NULL) AS has_attendance
  FROM `teamster-332318`.`kipptaf_students`.`int_students__attendance_daily`
  GROUP BY sn, calendardate
)

SELECT
  u.__row,
  CASE
    WHEN ad.sn IS NULL THEN 'UNEXPLAINED'
    WHEN NOT ad.has_membership THEN 'A'
    WHEN NOT ad.has_attendance THEN 'B'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u
LEFT JOIN ad
  ON ad.sn = CAST(u.lea_student_identifier AS STRING)
  AND ad.calendardate = CAST(u.attendance_date AS DATE)
