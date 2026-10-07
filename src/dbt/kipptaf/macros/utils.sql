{% macro extract_source_project(relation="") %}
    regexp_extract(
        {% if relation %}{{ relation }}.{% endif %}_dbt_source_relation, r'(kipp\w+)_'
    )
{% endmacro %}

{% macro extract_region(table) %}
    initcap(regexp_extract({{ table }}._dbt_source_project, r'kipp(\w+)'))
{% endmacro %}

{# Miami vendor files through SY2025 carry the bare pre-Focus student number; the
   Focus student_number, and so the network student_number, is that number with an
   8400 prefix (#5149). `year` is the row's academic year and `project` the code
   location: extract_source_project() inside a union_relations CTE, or the
   _dbt_source_project column once it exists. #}
{% macro focus_student_number(id, year, project) -%}
    {{ id }} + if(
        {{ project }} = 'kippmiami' and {{ year }} <= 2025 and {{ id }} < 8400000000,
        8400000000,
        0
    )
{%- endmacro %}

{# Whether an individual-exception row applies right now. This is a macro
   rather than a column on the staging model, and that is the load-bearing
   part: the staging model is a TABLE, so a derived column would freeze
   current_date at build time. That table rebuilds only when someone edits the
   spreadsheet -- prod has gone 54 days between rebuilds -- so a materialized
   answer would keep an expired grant live indefinitely. Interpolated into
   dim_staff_cube_access, a view, it evaluates per identity read instead.

   A null on either date yields null, so the row is not live. That is
   deliberate: an access grant with no stated bound should deny rather than
   run forever. Both date columns carry an error-severity not_null, so a null
   is already a broken row; this stops it granting while the test reports it.

   Three callers, not seven. The four generic-test `config.where` clauses on
   stg_google_sheets__people__cube_access_individual_exceptions restate the
   predicate by hand because they cannot call this: dbt's generic-test config
   parser rejects project macros outright ("does not support using custom
   macros to populate configuration values"). `var()` works there, a macro does
   not. Keep the two in step by hand. #}
{% macro is_live_row(status_column, grant_date_column, expiry_date_column) %}
    {{ status_column }} = 'active'
    and {{ grant_date_column }} <= current_date('{{ var("local_timezone") }}')
    and {{ expiry_date_column }} >= current_date('{{ var("local_timezone") }}')
{% endmacro %}
