select *, from {{ source("pearson", "src_pearson__student_list_report") }}
