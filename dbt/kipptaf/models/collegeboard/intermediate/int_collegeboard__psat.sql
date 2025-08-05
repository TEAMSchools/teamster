select psat.*, xw.powerschool_student_number,
from {{ ref("stg_collegeboard__psat") }} as psat
left join
    {{ ref("stg_collegeboard__sat_id_crosswalk") }} as xw
    on psat.cb_id = xw.college_board_id
