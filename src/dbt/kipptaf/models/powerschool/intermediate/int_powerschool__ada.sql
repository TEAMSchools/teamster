SELECT
    mem._dbt_source_relation,
    mem.yearid,
    mem.studentid,
    ROUND(AVG(CAST(mem.attendancevalue AS FLOAT64)), 3) AS ada
FROM
    {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} AS mem
WHERE
    mem.membershipvalue = 1
    AND mem.calendardate <= CAST(CURRENT_TIMESTAMP() AS DATE)
GROUP BY
    mem._dbt_source_relation,
    mem.yearid,
    mem.studentid
