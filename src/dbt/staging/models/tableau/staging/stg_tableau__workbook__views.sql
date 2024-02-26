select
    w._dagster_partition_fiscal_year as fiscal_year,
    w._dagster_partition_date as `date`,
    w.id as workbook_id,
    w.name as workbook_name,
    w.owner_id as workbook_owner_id,
    w.project_id as workbook_project_id,
    w.project_name as workbook_project_name,
    w.webpage_url as workbook_webpage_url,
    w.content_url as workbook_content_url,
    w.size as workbook_size,
    w.show_tabs as workbook_show_tabs,

    v.id as view_id,
    v.name as view_name,
    v.owner_id as view_owner_id,
    v.project_id as view_project_id,
    v.content_url as view_content_url,
    v.total_views as view_total_views,
from {{ source("tableau", "src_tableau__workbook") }} as w
cross join unnest(views) as v
