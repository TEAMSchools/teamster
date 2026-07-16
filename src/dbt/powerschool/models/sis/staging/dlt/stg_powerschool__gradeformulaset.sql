select
    * replace (
        cast(gradeformulasetid as int) as gradeformulasetid,
        cast(iscoursegradecalculated as int) as iscoursegradecalculated,
        cast(isreporttermsetupsame as int) as isreporttermsetupsame,
        cast(sectionsdcid as int) as sectionsdcid,
        cast(yearid as int) as yearid
    ),
from {{ source("powerschool_dlt", "gradeformulaset") }}
