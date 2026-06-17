-- BigQuery forbids WITH RECURSIVE inside dbt's wrapped CTAS/view DDL, so the
-- transitive closure is unrolled as bounded self-joins of the direct manager
-- edges. max_depth is a generous backstop; current org data tops out at 7.
{% set max_depth = 10 %}

with
    direct_edges as (
        select
            swa.staff_key as descendant_staff_key,

            rr.manager_staff_key as ancestor_staff_key,
        from {{ ref("dim_work_assignment_primary") }} as wap
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wap.work_assignment_key = swa.work_assignment_key
        inner join
            {{ ref("dim_work_assignment_reporting_relationships") }} as rr
            on wap.work_assignment_key = rr.work_assignment_key
            and rr.is_current
        where
            wap.is_primary_position
            and wap.is_current
            and swa.staff_key is not null
            and rr.manager_staff_key is not null
    ),

    all_staff as (select staff_key, from {{ ref("dim_staff") }}),

    closure as (
        -- depth 0: every staff member is in their own reporting chain so a
        -- manager resolves to their own data, not only their reports
        select
            staff_key as ancestor_staff_key,
            staff_key as descendant_staff_key,
            0 as depth,
        from all_staff

        {% for k in range(1, max_depth + 1) %}
            union all

            select
                e0.ancestor_staff_key,
                e{{ k - 1 }}.descendant_staff_key,
                {{ k }} as depth,
            from direct_edges as e0
            {%- for j in range(1, k) %}
                inner join
                    direct_edges as e{{ j }}
                    on e{{ j - 1 }}.descendant_staff_key = e{{ j }}.ancestor_staff_key
            {%- endfor %}
        {% endfor %}
    ),

    deduped as (
        select ancestor_staff_key, descendant_staff_key, min(depth) as depth,
        from closure
        group by ancestor_staff_key, descendant_staff_key
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["ancestor_staff_key", "descendant_staff_key"]
        )
    }} as staff_hierarchy_key, ancestor_staff_key, descendant_staff_key, depth,
from deduped
