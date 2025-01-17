select
    psat.*,
    xw.powerschool_student_number,
    case
        psat.test_type
        when 'PSAT89'
        then 'psat89'
        when 'PSATNM'
        then 'psatnmsqt'
        when 'PSAT10'
        then 'psat10'
    end as test_name
from {{ ref("stg_collegeboard__psat") }} as psat
left join
    {{ ref("stg_collegeboard__id_crosswalk") }} as xw
    on psat.cb_id = xw.college_board_id
