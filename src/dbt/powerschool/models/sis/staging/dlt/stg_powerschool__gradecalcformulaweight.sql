select
    * except (primaryweight) replace (
        cast(assignmentid as int) as assignmentid,
        cast(districtteachercategoryid as int) as districtteachercategoryid,
        cast(gradecalcformulaweightid as int) as gradecalcformulaweightid,
        cast(gradecalculationtypeid as int) as gradecalculationtypeid,
        cast(teachercategoryid as int) as teachercategoryid
    ),
from {{ source("powerschool_dlt", "gradecalcformulaweight") }}
