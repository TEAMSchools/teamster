select
    * replace (
        cast(gradeformulasetid as int) as gradeformulasetid,
        cast(gradeschoolconfigid as int) as gradeschoolconfigid,
        cast(gradeschoolformulaassocid as int) as gradeschoolformulaassocid,
        cast(isdefaultformulaset as int) as isdefaultformulaset
    ),
from {{ source("powerschool_dlt", "gradeschoolformulaassoc") }}
