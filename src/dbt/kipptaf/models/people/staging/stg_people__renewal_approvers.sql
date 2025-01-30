select *, from {{ source("people", "src_people__renewal_approvers") }}
