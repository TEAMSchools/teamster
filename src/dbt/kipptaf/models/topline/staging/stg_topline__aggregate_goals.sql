select * from {{ source("topline", "src_topline__aggregate_goals") }}
