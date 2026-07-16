select
    * replace (
        cast(dcid as int) as dcid,
        cast(gradebooktype as int) as gradebooktype,
        cast(id as int) as id,
        cast(isexempt as int) as isexempt,
        cast(isincomplete as int) as isincomplete,
        cast(sectionid as int) as sectionid,
        cast(studentid as int) as studentid,
        cast(whomodifiedid as int) as whomodifiedid,

        cast(calculatedpercent as float64) as calculatedpercent,
        cast(percent as float64) as `percent`,
        cast(points as float64) as points,
        cast(pointspossible as float64) as pointspossible,
        cast(varcredit as float64) as varcredit,

        cast(enddate as date) as enddate,
        cast(lastgradeupdate as date) as lastgradeupdate,
        cast(startdate as date) as startdate
    ),

    -- not populated by dlt ingestion (sftp-only partition metadata / enrichment)
    cast(null as int64) as _dagster_partition_fiscal_year,
    cast(null as date) as _dagster_partition_date,
    cast(null as int64) as _dagster_partition_hour,
    cast(null as int64) as _dagster_partition_minute,
    cast(null as float64) as percent_decimal,
    cast(null as float64) as percent_decimal_adjusted,
    cast(null as string) as grade_adjusted,
from {{ source("powerschool_dlt", "pgfinalgrades") }}
