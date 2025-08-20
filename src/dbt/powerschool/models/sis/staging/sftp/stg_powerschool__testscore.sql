{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (dcid, id, testid, sortorder),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    testid.int_value as testid,
    sortorder.int_value as sortorder,
from {{ source("powerschool_sftp", "src_powerschool__testscore") }}
