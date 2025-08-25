select
    * except (
        confidentialcommflag,
        enddate,
        excludefromstatereportingflg,
        generalcommflag,
        isactive,
        iscustodial,
        isemergency,
        liveswithflg,
        receivesmailflg,
        relationshiptypecodesetid,
        schoolpickupflg,
        startdate,
        studentcontactassocid,
        studentcontactdetailid,
        whencreated,
        whenmodified
    ),

    cast(confidentialcommflag as int) as confidentialcommflag,
    cast(excludefromstatereportingflg as int) as excludefromstatereportingflg,
    cast(generalcommflag as int) as generalcommflag,
    cast(isactive as int) as isactive,
    cast(iscustodial as int) as iscustodial,
    cast(isemergency as int) as isemergency,
    cast(liveswithflg as int) as liveswithflg,
    cast(receivesmailflg as int) as receivesmailflg,
    cast(relationshiptypecodesetid as int) as relationshiptypecodesetid,
    cast(schoolpickupflg as int) as schoolpickupflg,
    cast(studentcontactassocid as int) as studentcontactassocid,
    cast(studentcontactdetailid as int) as studentcontactdetailid,

    cast(startdate as date) as startdate,
    cast(enddate as date) as enddate,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__studentcontactdetail") }}
