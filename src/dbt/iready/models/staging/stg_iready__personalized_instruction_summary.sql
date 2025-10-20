select *, from {{ source("iready", "src_iready__personalized_instruction_summary") }}
