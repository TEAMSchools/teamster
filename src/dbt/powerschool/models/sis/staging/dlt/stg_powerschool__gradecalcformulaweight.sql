select
    storecode,
    `type`,
    stndcalculationmetric,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,
    `weight`,

    cast(gradecalcformulaweightid as int) as gradecalcformulaweightid,
    cast(gradecalculationtypeid as int) as gradecalculationtypeid,
    cast(teachercategoryid as int) as teachercategoryid,
    cast(districtteachercategoryid as int) as districtteachercategoryid,
    cast(assignmentid as int) as assignmentid,
from {{ source("powerschool_dlt", "gradecalcformulaweight") }}
