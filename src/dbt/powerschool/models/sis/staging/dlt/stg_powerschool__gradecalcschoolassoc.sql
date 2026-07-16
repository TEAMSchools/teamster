select
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(gradecalcschoolassocid as int) as gradecalcschoolassocid,
    cast(gradecalculationtypeid as int) as gradecalculationtypeid,
    cast(schoolsdcid as int) as schoolsdcid,
from {{ source("powerschool_dlt", "gradecalcschoolassoc") }}
