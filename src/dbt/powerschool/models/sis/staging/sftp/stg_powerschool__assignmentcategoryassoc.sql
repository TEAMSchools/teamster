select
    * except (
        _dagster_partition_date,
        _dagster_partition_fiscal_year,
        _dagster_partition_hour,
        _dagster_partition_minute,
        source_file_name
    ),
from {{ source("powerschool_sftp", "src_powerschool__assignmentcategoryassoc") }}
