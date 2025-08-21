select
    * except (
        att_flags,
        att_interval,
        attendance_codeid,
        calendar_dayid,
        ccid,
        dcid,
        id,
        lock_reporting_yn,
        lock_teacher_yn,
        parent_attendanceid,
        periodid,
        programid,
        schoolid,
        studentid,
        total_minutes,
        whomodifiedid,
        yearid,
        ada_value_code,
        ada_value_time,
        adm_value,
        att_date,
        transaction_date
    ),

    cast(att_flags as int) as att_flags,
    cast(att_interval as int) as att_interval,
    cast(attendance_codeid as int) as attendance_codeid,
    cast(calendar_dayid as int) as calendar_dayid,
    cast(ccid as int) as ccid,
    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(lock_reporting_yn as int) as lock_reporting_yn,
    cast(lock_teacher_yn as int) as lock_teacher_yn,
    cast(parent_attendanceid as int) as parent_attendanceid,
    cast(periodid as int) as periodid,
    cast(programid as int) as programid,
    cast(schoolid as int) as schoolid,
    cast(studentid as int) as studentid,
    cast(total_minutes as int) as total_minutes,
    cast(whomodifiedid as int) as whomodifiedid,
    cast(yearid as int) as yearid,

    cast(ada_value_code as float64) as ada_value_code,
    cast(ada_value_time as float64) as ada_value_time,
    cast(adm_value as float64) as adm_value,

    cast(att_date as date) as att_date,

    cast(transaction_date as timestamp) as transaction_date,
{# 
| _dagster_partition_date        || DATE    | missing in definition |
| _dagster_partition_fiscal_year || INT64   | missing in definition |
| _dagster_partition_hour        || INT64   | missing in definition |
| _dagster_partition_minute      || INT64   | missing in definition |
| executionid                    || STRING  | missing in definition |
#}
from {{ source("powerschool_sftp", "src_powerschool__attendance") }}
