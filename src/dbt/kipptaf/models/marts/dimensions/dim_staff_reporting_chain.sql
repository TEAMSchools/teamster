{#-
  Transitive closure of the CURRENT org tree, keyed on staff_key. One row per
  (manager_staff_key, reportee_staff_key) reachable through the reporting chain,
  plus a depth-0 self-pair per staff. Read by cube.js's resolveAccess to grant a
  manager PII access to their own downline (the staff-pii-reporting_chain scope).
  Edges are the current-slice rows of dim_staff_reporting_periods (the period
  covering today), so the closure reflects today's org.

  Uses WITH RECURSIVE, so this model sets contract: enforced: false — contract
  validation wraps the model SQL in a subquery, and BigQuery only allows
  WITH RECURSIVE at the top level of a statement.

  Isolated-node gap: all_staff derives exclusively from edges
  (dim_staff_reporting_periods, current slice). A staff member with no current
  reporting relationship row at all — no manager, no direct reports — will not
  appear in all_staff and therefore receives no self-pair. For the
  staff-pii-reporting_chain scope, this means reportee_staff_keys resolves to []
  and the staff_pii row_level filter denies access as if they had no downline. In
  practice virtually all KTAF staff have at
  least one reporting relationship, but a newly-hired executive before their
  direct reports are loaded, or an ADP data-quality gap, will hit this silently.
  Debug by checking dim_staff_reporting_periods for the affected staff_key.
-#}
with recursive
    -- Current-slice reporting edges. The period-intersection edge derivation
    -- lives once in dim_staff_reporting_periods (all history, already filtered to
    -- primary-position, non-null staff_key); here we take the period covering
    -- today and restrict to currently-employed staff (active or leave) via
    -- dim_staff_work_assignments.is_current, so the closure reflects today's org
    -- for the PII access scope. This excludes terminated staff whose stale
    -- open-ended ADP reporting periods would otherwise cover today.
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    raw_edges as (
        select rp.staff_key as reportee_staff_key, rp.manager_staff_key,
        from {{ ref("dim_staff_reporting_periods") }} as rp
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on rp.staff_key = swa.staff_key
            and swa.is_current
        where
            rp.manager_staff_key is not null
            and current_date('{{ var("local_timezone") }}')
            between rp.effective_start_date and rp.effective_end_date
    ),

    -- TODO: a small number of active+primary staff can carry two current
    -- reporting relationships; dedupe to one manager per reportee
    -- deterministically until the upstream ADP data is corrected. The
    -- order_by is an arbitrary (but stable) tiebreaker on manager_staff_key,
    -- not a business rule -- dim_work_assignment_reporting_relationships
    -- carries effective_start_date, which could pick the most-recent
    -- relationship instead; left as-is pending a product decision on which
    -- manager should win.
    edges as (
        {{
            dbt_utils.deduplicate(
                relation="raw_edges",
                partition_by="reportee_staff_key",
                order_by="manager_staff_key",
            )
        }}
    ),

    closure as (
        select manager_staff_key, reportee_staff_key, 1 as depth,
        from edges

        union all

        select c.manager_staff_key, e.reportee_staff_key, c.depth + 1 as depth,
        from closure as c
        inner join edges as e on c.reportee_staff_key = e.manager_staff_key
        where c.depth < 20
    ),

    all_staff as (
        select reportee_staff_key as staff_key,
        from edges
        union distinct
        select manager_staff_key as staff_key,
        from edges
    ),

    combined as (
        select manager_staff_key, reportee_staff_key, depth,
        from closure

        union all

        select
            staff_key as manager_staff_key, staff_key as reportee_staff_key, 0 as depth,
        from all_staff
    )

select manager_staff_key, reportee_staff_key, min(depth) as depth,
from combined
group by manager_staff_key, reportee_staff_key
