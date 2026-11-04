select
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(gradeschoolformulaassocid as int) as gradeschoolformulaassocid,
    cast(gradeformulasetid as int) as gradeformulasetid,
    cast(gradeschoolconfigid as int) as gradeschoolconfigid,
    cast(isdefaultformulaset as int) as isdefaultformulaset,
from {{ source("powerschool_dlt", "gradeschoolformulaassoc") }}
