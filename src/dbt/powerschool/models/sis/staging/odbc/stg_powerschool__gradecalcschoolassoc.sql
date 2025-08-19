{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    * except (gradecalcschoolassocid, gradecalculationtypeid, schoolsdcid),

    /* column transformations */
    gradecalcschoolassocid.int_value as gradecalcschoolassocid,
    gradecalculationtypeid.int_value as gradecalculationtypeid,
    schoolsdcid.int_value as schoolsdcid,
from {{ source("powerschool", "src_powerschool__gradecalcschoolassoc") }}
