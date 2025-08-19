{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    * except (
        studentcontactdetailid,
        studentcontactassocid,
        relationshiptypecodesetid,
        isactive,
        isemergency,
        iscustodial,
        liveswithflg,
        schoolpickupflg,
        receivesmailflg,
        excludefromstatereportingflg,
        generalcommflag,
        confidentialcommflag
    ),

    /* column transformations */
    studentcontactdetailid.int_value as studentcontactdetailid,
    studentcontactassocid.int_value as studentcontactassocid,
    relationshiptypecodesetid.int_value as relationshiptypecodesetid,
    isactive.int_value as isactive,
    isemergency.int_value as isemergency,
    iscustodial.int_value as iscustodial,
    liveswithflg.int_value as liveswithflg,
    schoolpickupflg.int_value as schoolpickupflg,
    receivesmailflg.int_value as receivesmailflg,
    excludefromstatereportingflg.int_value as excludefromstatereportingflg,
    generalcommflag.int_value as generalcommflag,
    confidentialcommflag.int_value as confidentialcommflag,
from {{ source("powerschool", "src_powerschool__studentcontactdetail") }}
