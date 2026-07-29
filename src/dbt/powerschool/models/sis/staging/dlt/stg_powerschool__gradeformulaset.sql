select
    `name`,
    `description`,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,
    `type`,

    cast(gradeformulasetid as int) as gradeformulasetid,
    cast(yearid as int) as yearid,
    cast(iscoursegradecalculated as int) as iscoursegradecalculated,
    cast(isreporttermsetupsame as int) as isreporttermsetupsame,
    cast(sectionsdcid as int) as sectionsdcid,
from {{ source("powerschool_dlt", "gradeformulaset") }}
