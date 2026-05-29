select a.ap_number_ap_id,
from {{ ref("stg_collegeboard__ap") }} as a
left join
    {{ ref("stg_google_sheets__collegeboard__ap_id_crosswalk") }} as x
    on a.ap_number_ap_id = x.college_board_id
where x.college_board_id is null
