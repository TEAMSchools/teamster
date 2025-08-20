{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (
        gradecalcformulaweightid,
        gradecalculationtypeid,
        teachercategoryid,
        districtteachercategoryid,
        assignmentid,
        `weight`
    ),

    /* column transformations */
    gradecalcformulaweightid.int_value as gradecalcformulaweightid,
    gradecalculationtypeid.int_value as gradecalculationtypeid,
    teachercategoryid.int_value as teachercategoryid,
    districtteachercategoryid.int_value as districtteachercategoryid,
    assignmentid.int_value as assignmentid,
    weight.bytes_decimal_value as `weight`,
from {{ source("powerschool_sftp", "src_powerschool__gradecalcformulaweight") }}
