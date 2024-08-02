
WITH snapshot_archive AS (
  SELECT
    staffing_model_id,
    export_date,
    valid_to,
    staffing_status,
    status_detail,
    is_mid_year_hire,
    plan_status,
    academic_year,
    teammate,
    is_open,
    is_active,
    is_staffed,
    is_new_hire,
    ROW_NUMBER() OVER (PARTITION BY staffing_model_id ORDER BY export_date) AS rn
  FROM
    {{ ref('stg_seat_tracker__log_archive') }}
),
previous_data AS (
  SELECT
    c.staffing_model_id,
    c.export_date AS current_export_date,
    c.valid_to AS current_valid_to,
    c.staffing_status AS current_staffing_status,
    c.status_detail AS current_status_detail,
    c.is_mid_year_hire AS current_is_mid_year_hire,
    c.plan_status AS current_plan_status,
    c.academic_year AS current_academic_year,
    c.teammate AS current_teammate,
    c.is_open AS current_is_open,
    c.is_active AS current_is_active,
    c.is_staffed AS current_is_staffed,
    c.is_new_hire AS current_is_new_hire,
    COALESCE(p.export_date, DATE_ADD(c.export_date, INTERVAL 6 DAY)) AS next_valid_from,
    p.valid_to AS previous_valid_to,
    p.staffing_status AS previous_staffing_status,
    p.status_detail AS previous_status_detail,
    p.is_mid_year_hire AS previous_is_mid_year_hire,
    p.plan_status AS previous_plan_status,
    p.academic_year AS previous_academic_year,
    p.teammate AS previous_teammate,
    p.is_open AS previous_is_open,
    p.is_active AS previous_is_active,
    p.is_staffed AS previous_is_staffed,
    p.is_new_hire AS previous_is_new_hire
  FROM
    snapshot_archive AS c
  LEFT JOIN
    snapshot_archive AS p
  ON
    c.staffing_model_id = p.staffing_model_id
    AND c.rn = p.rn + 1
),
archive_change_log AS (
  SELECT
    current_export_date AS valid_from,
    LEAD(current_export_date, 1) OVER (PARTITION BY staffing_model_id ORDER BY current_export_date) - INTERVAL 1 DAY AS valid_to,
    staffing_model_id,
    current_staffing_status AS staffing_status,
    current_status_detail AS status_detail,
    current_is_mid_year_hire AS is_mid_year_hire,
    current_plan_status AS plan_status,
    current_academic_year AS academic_year,
    current_teammate AS teammate,
    current_is_open AS is_open,
    current_is_active AS is_active,
    current_is_staffed AS is_staffed,
    current_is_new_hire AS is_new_hire
  FROM
    previous_data
  WHERE
    previous_valid_to IS NULL
    OR (
      current_is_open IS DISTINCT FROM previous_is_open
      OR current_is_mid_year_hire IS DISTINCT FROM previous_is_mid_year_hire
      OR current_is_active IS DISTINCT FROM previous_is_active
      OR current_is_staffed IS DISTINCT FROM previous_is_staffed
      OR current_is_new_hire IS DISTINCT FROM previous_is_new_hire
      OR current_teammate IS DISTINCT FROM previous_teammate
    )
)

select
    academic_year as snapshot_academic_year,
    staffing_model_id as snapshot_staffing_model_id,
    teammate as snapshot_teammate,
    staffing_status as snapshot_staffing_status,
    status_detail as snapshot_status_detail,
    plan_status as snapshot_plan_status,
    is_mid_year_hire as snapshot_mid_year_hire,
    if(is_mid_year_hire, 1, 0) as snapshot_mid_year_hire_int,

    if(is_open, 1, 0) as snapshot_open,
    if(is_new_hire, 1, 0) as snapshot_new_hire,
    if(is_staffed, 1, 0) as snapshot_staffed,
    if(is_active, 1, 0) as snapshot_active,
    cast(valid_from as timestamp) as valid_from,
    cast(valid_to as timestamp) as valid_to,

from archive_change_log as a
left join {{ ref('snapshot__seat_tracker__seats') }} as s

union all

select
    cast(academic_year as string) as snapshot_academic_year,
    staffing_model_id as snapshot_staffing_model_id,
    cast(teammate as string) as snapshot_teammate,
    staffing_status as snapshot_staffing_status,
    status_detail as snapshot_status_detail,
    plan_status as snapshot_plan_status,
    mid_year_hire as snapshot_mid_year_hire,
    is_mid_year_hire_int as snapshot_mid_year_hire_int,

    if(is_open, 1, 0) as snapshot_open,
    if(is_new_hire, 1, 0) as snapshot_new_hire,
    if(is_staffed, 1, 0) as snapshot_staffed,
    if(is_active, 1, 0) as snapshot_active,
    dbt_valid_from as valid_from,
    dbt_valid_to as valid_to,

from {{ ref("snapshot__seat_tracker__seats") }}
where dbt_updated_at > ('2024-08-01')