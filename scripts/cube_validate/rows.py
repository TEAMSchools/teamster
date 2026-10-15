"""Rows layer: join the extract's rows to Cube's, and give each exactly 1 bucket."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Checks, lit, side_sql

TAB = '"tab"."Extract"."Extract"'
CUB = '"cub"."cube"."rows"'
CAUSED = ("value_differs", "dashboard_only", "cube_only")
T_BUCKETS = ("match", "value_differs", "dashboard_only", "outside_scope")
C_BUCKETS = ("match", "value_differs", "cube_only")


class RowsError(RuntimeError):
    """The tool's own cause list or join broke a rule. Data never raises this."""


@dataclass
class RowsResult:
    totals: dict[str, int]
    buckets: list[dict]
    differing_columns: dict[str, int]
    invariants: dict[str, bool]


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _side(ws, checks: Checks, alias: str, schema: str, table: str, p: str) -> str:
    """One side's rows: raw columns prefixed, plus key, compare and label values."""
    side = "tableau" if p == "t" else "cube"
    src = f'"{alias}"."{schema}"."{table}"'
    cols = [f"{_q(c)} as {_q(f'{p}_{c}')}" for c in ws.columns(alias, schema, table)]
    keys = [
        f"({side_sql(getattr(e, side), '')}) as {_q(f'{p}__k_{e.name}')}"
        for e in checks.key
    ]
    vals = [
        f"({side_sql(getattr(e, side), '')}) as {_q(f'{p}__v_{e.name}')}"
        for e in checks.compare
    ]
    labs = [
        f"({side_sql(getattr(e, side), '')}) as {_q(f'{p}__l_{e.name}')}"
        for e in checks.labels
    ]
    part = ", ".join(f"({side_sql(getattr(e, side), '')})" for e in checks.key)
    # Order by the compare values, then every raw column, so equal-valued
    # duplicates pair first and a rerun on one snapshot gives the same buckets.
    order = ", ".join(
        [
            *(f"({side_sql(getattr(e, side), '')})" for e in checks.compare),
            *(_q(c) for c in ws.columns(alias, schema, table)),
        ]
    )
    dup = (
        f"row_number() over (partition by {part} order by {order}) as {_q(f'{p}__dup')}"
    )
    sel = ", ".join([*cols, *keys, *vals, *labs, dup, f"true as {_q(f'{p}__in')}"])
    # trunk-ignore(bandit/B608): identifiers are quoted and values come from the checks file, never user input
    return f"select {sel} from {src}"


def build(ws, checks: Checks, scope: list[str]) -> RowsResult:
    """Join both sides into table `rows` with a base bucket and a cause per row.

    Args:
        ws: A hyper.Workspace with the extract attached as "tab" and Cube's rows
            as "cub".
        checks: The checks file.
        scope: The scope key's values Cube can see; dashboard-only rows outside
            it are "outside_scope".

    Returns:
        Totals, bucket counts, differing-column counts and the 2 balance
        invariants.

    Raises:
        RowsError: 2 causes claim the same row.
    """
    t = _side(ws, checks, "tab", "Extract", "Extract", "t")
    c = _side(ws, checks, "cub", "cube", "rows", "c")
    on = " and ".join(
        [f"t.{_q(f't__k_{e.name}')} = c.{_q(f'c__k_{e.name}')}" for e in checks.key]
        + ['t."t__dup" = c."c__dup"']
    )
    keys = [
        f"coalesce(t.{_q(f't__k_{e.name}')}, c.{_q(f'c__k_{e.name}')}) as {_q(f'k_{e.name}')}"
        for e in checks.key
    ]
    labels = [
        f"coalesce(t.{_q(f't__l_{e.name}')}, c.{_q(f'c__l_{e.name}')}) as {_q(f'l_{e.name}')}"
        for e in checks.labels
    ]
    diffs = [
        f"not (t.{_q(f't__v_{e.name}')} is not distinct from c.{_q(f'c__v_{e.name}')}) as {_q(f'd_{e.name}')}"
        for e in checks.compare
    ]
    joined = (
        'select t.*, c.*, coalesce(t."t__in", false) as in_t, coalesce(c."c__in", false) as in_c, '
        + ", ".join([*keys, *labels, *diffs])
        + f" from ({t}) t full outer join ({c}) c on {on}"
    )
    any_diff = " or ".join(f"j.{_q(f'd_{e.name}')}" for e in checks.compare) or "false"
    if checks.scope_key and scope:
        k = f"j.{_q(f'k_{checks.scope_key}')}"
        outside = f"{k} is null or {k} not in ({', '.join(lit(s) for s in scope)})"
    else:
        outside = "false"
    base = (
        f"case when j.in_t and j.in_c then case when {any_diff} then 'value_differs' else 'match' end "
        f"when j.in_t then case when {outside} then 'outside_scope' else 'dashboard_only' end "
        "else 'cube_only' end"
    )
    ws.execute(
        # trunk-ignore(bandit/B608): identifiers are quoted and values come from the checks file, never user input
        f"create temporary table rows_base as select j.*, {base} as base from ({joined}) j"
    )

    caused = ", ".join(lit(b) for b in CAUSED)
    if checks.causes:
        flags = ", ".join(
            f"case when base in ({caused}) and ({x.where}) then 1 else 0 end as {_q(f'z_{i}')}"
            for i, x in enumerate(checks.causes)
        )
        total = " + ".join(_q(f"z_{i}") for i in range(len(checks.causes)))
        cols = ", ".join(_q(f"z_{i}") for i in range(len(checks.causes)))
        over = ws.query(
            # trunk-ignore(bandit/B608): identifiers are quoted and values come from the checks file, never user input
            f"select {cols}, count(*) from (select {flags} from rows_base) z where {total} > 1 group by {cols}"
        )
        if over:
            msgs = []
            for r in over:
                ids = ", ".join(
                    x.id for x, f in zip(checks.causes, r[:-1], strict=True) if f
                )
                msgs.append(f"{ids} ({r[-1]} rows)")
            raise RowsError(
                "causes overlap, so a row would get 2 causes: " + "; ".join(msgs)
            )
    whens = " ".join(f"when ({x.where}) then {lit(x.id)}" for x in checks.causes)
    cause = (
        "case when base = 'match' then null when base = 'outside_scope' then 'outside_scope' "
        f"{whens} else 'unexplained' end"
    )
    ws.execute(
        # trunk-ignore(bandit/B608): identifiers are quoted and values come from the checks file, never user input
        f"create temporary table rows as select *, {cause} as cause from rows_base"
    )
    ws.execute("drop table rows_base")
    return _summarize(ws, checks)


def _summarize(ws, checks: Checks) -> RowsResult:
    labels = [f"l_{e.name}" for e in checks.labels]
    month = f"cast(date_trunc('month', {_q(f'k_{checks.date_key}')}) as date)"
    group = [*(_q(n) for n in labels), month, "base", "cause"]
    sel = ", ".join(
        [
            *(f"{_q(n)} as {_q(n[2:])}" for n in labels),
            f"{month} as month",
            "base",
            "cause",
        ]
    )
    buckets = ws.dicts(
        # trunk-ignore(bandit/B608): identifiers are quoted and values come from the checks file, never user input
        f"select {sel}, count(*) as rows, count(distinct {_q(f'k_{checks.student_key}')}) as students "
        f"from rows group by {', '.join(group)} order by {', '.join(group)}"
    )
    n_tab, n_cub = ws.count(TAB), ws.count(CUB)
    n_join = ws.count("rows")
    in_t, in_c = ws.count("rows where in_t"), ws.count("rows where in_c")
    t_sum = ws.count(f"rows where base in ({', '.join(lit(b) for b in T_BUCKETS)})")
    c_sum = ws.count(f"rows where base in ({', '.join(lit(b) for b in C_BUCKETS)})")
    differing = {}
    for e in checks.compare:
        differing[e.name] = ws.count(
            f"rows where base = 'value_differs' and {_q(f'd_{e.name}')}"
        )
    return RowsResult(
        totals={"tableau": n_tab, "cube": n_cub, "joined": n_join},
        buckets=buckets,
        differing_columns={k: v for k, v in differing.items() if v},
        invariants={
            "dashboard rows balance": n_tab == in_t == t_sum,
            "Cube rows balance": n_cub == in_c == c_sum,
        },
    )
