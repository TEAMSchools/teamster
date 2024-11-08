with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__studentcontactdetail"
                ),
                partition_by="studentcontactdetailid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
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
from deduplicate
