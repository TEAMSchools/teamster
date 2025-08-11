{# TODO: add student/week scaffold #}
select *, from {{ ref("snapshot_kippadb__standardized_test_rollup") }}
