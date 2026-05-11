select
    * except (primaryweight) replace (
        gradecalcformulaweightid.int_value as gradecalcformulaweightid,
        gradecalculationtypeid.int_value as gradecalculationtypeid,
        teachercategoryid.int_value as teachercategoryid,
        districtteachercategoryid.int_value as districtteachercategoryid,
        assignmentid.int_value as assignmentid,
        weight.bytes_decimal_value as `weight`
    ),
from {{ source("powerschool_odbc", "src_powerschool__gradecalcformulaweight") }}
