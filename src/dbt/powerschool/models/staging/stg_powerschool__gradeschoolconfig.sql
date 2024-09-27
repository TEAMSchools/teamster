with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__gradeschoolconfig"),
                partition_by="gradeschoolconfigid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        gradeschoolconfigid,
        schoolsdcid,
        yearid,
        defaultdecimalcount,
        iscalcformulaeditable,
        isdropscoreeditable,
        iscalcprecisioneditable,
        iscalcmetriceditable,
        isrecentscoreeditable,
        ishigherstndautocalc,
        ishigherstndcalceditable,
        ishighstandardeditable,
        iscalcmetricschooledit,
        isstandardsshown,
        isstandardsshownonasgmt,
        istraditionalgradeshown,
        iscitizenshipdisplayed,
        termbinlockoffset,
        lockwarningoffset,
        issectstndweighteditable,
        minimumassignmentvalue,
        isgradescaleteachereditable,
        isstandardslimited,
        isstandardslimitededitable,
        isusingpercentforstndautocalc
    ),

    /* column transformations */
    gradeschoolconfigid.int_value as gradeschoolconfigid,
    schoolsdcid.int_value as schoolsdcid,
    yearid.int_value as yearid,
    defaultdecimalcount.int_value as defaultdecimalcount,
    iscalcformulaeditable.int_value as iscalcformulaeditable,
    isdropscoreeditable.int_value as isdropscoreeditable,
    iscalcprecisioneditable.int_value as iscalcprecisioneditable,
    iscalcmetriceditable.int_value as iscalcmetriceditable,
    isrecentscoreeditable.int_value as isrecentscoreeditable,
    ishigherstndautocalc.int_value as ishigherstndautocalc,
    ishigherstndcalceditable.int_value as ishigherstndcalceditable,
    ishighstandardeditable.int_value as ishighstandardeditable,
    iscalcmetricschooledit.int_value as iscalcmetricschooledit,
    isstandardsshown.int_value as isstandardsshown,
    isstandardsshownonasgmt.int_value as isstandardsshownonasgmt,
    istraditionalgradeshown.int_value as istraditionalgradeshown,
    iscitizenshipdisplayed.int_value as iscitizenshipdisplayed,
    termbinlockoffset.int_value as termbinlockoffset,
    lockwarningoffset.int_value as lockwarningoffset,
    issectstndweighteditable.int_value as issectstndweighteditable,
    minimumassignmentvalue.int_value as minimumassignmentvalue,
    isgradescaleteachereditable.int_value as isgradescaleteachereditable,
    isstandardslimited.int_value as isstandardslimited,
    isstandardslimitededitable.int_value as isstandardslimitededitable,
    isusingpercentforstndautocalc.int_value as isusingpercentforstndautocalc,
from deduplicate
