/* TODO(#3908): remove this spoof once Paterson gets its own U_EXPECTATIONS source
   native plugin support or another data path). Paterson's PowerSchool instance cannot
   run the KIPP NJ Gradebook Audit plugin, so U_EXPECTATIONS is never populated here.
   Spoof MS expectations from Newark's real plugin data until a native solution exists
   — see docs/reference/gradebook-audit-data-model.md "Paterson GradeBook plugin". */
select
    id,
    school_level,
    `quarter`,
    week_number,
    cnt_w,
    cnt_h,
    cnt_f,
    cnt_s,
    notes,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,
from {{ source("kippnewark_powerschool", "stg_powerschool__u_expectations") }}
where school_level = 'MS'
