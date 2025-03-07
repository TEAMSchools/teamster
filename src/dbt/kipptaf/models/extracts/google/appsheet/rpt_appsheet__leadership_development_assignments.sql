select
    ldr.employee_number,
    ldr.entity,
    ldm.region,

    ldm.academic_year,
    ldm.metric_id,

    concat(ldr.employee_number, ldm.metric_id) as assignment_id,
from {{ ref("rpt_appsheet__leadership_development_roster") }} as ldr
inner join
    {{ ref("stg_performance_management__leadership_development_metrics") }} as ldm
    on ldr.route = ldm.role
    and ldr.entity = ldm.region

union all

select
    ldr.employee_number,
    ldr.entity,
    ldm.region,

    ldm.academic_year,
    ldm.metric_id,

    concat(ldr.employee_number, ldm.metric_id) as assignment_id,
from {{ ref("rpt_appsheet__leadership_development_roster") }} as ldr
inner join
    {{ ref("stg_performance_management__leadership_development_metrics") }} as ldm
    on ldr.route = ldm.role
    and ldm.region = 'All'
