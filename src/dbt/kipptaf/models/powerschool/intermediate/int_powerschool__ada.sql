SELECT
    co.academic_year,
    co.student_number,
    ROUND(AVG(CAST(mem.attendancevalue AS FLOAT64)), 3) AS ada
FROM
    {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} AS mem
INNER JOIN
    {{ ref("base_powerschool__student_enrollments") }} AS co
    ON
        (
            mem.studentid = co.studentid
            AND mem.yearid = co.yearid
            AND co.rn_year = 1
            AND co.is_enrolled_y1
    AND {{ union_dataset_join_clause(left_alias="mem", right_alias="co") }}
        )
WHERE
    mem.membershipvalue = 1
    AND mem.calendardate <= CAST(CURRENT_TIMESTAMP() AS DATE)
GROUP BY
    co.academic_year,
    co.student_number
