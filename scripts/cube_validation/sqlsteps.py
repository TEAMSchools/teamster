"""Find the steps of a query that can drop a row, and neutralize them.

A step is one place a query can drop a row: a WHERE or HAVING conjunct, an
INNER JOIN, a LEFT JOIN a later predicate requires, or an INNER JOIN's ON
conjunct other than a key equality (which filters as a WHERE conjunct would).
A row pick (QUALIFY, or `rn = 1` on a ROW_NUMBER or RANK column) is never a
step: neutralizing it brings back another row of the same key, not the row.
Steps are found in every SELECT, CTE, subquery and inlined view that can
change which rows the query returns; the rest (a CTE nothing reads, a LEFT
JOIN that feeds no output key and nothing requires, a UNION branch whose
student column is NULL, a scalar or NOT IN / NOT EXISTS subquery) are pruned.

To neutralize steps, a select is first rewritten to an equal canonical form:
every INNER JOIN becomes a LEFT JOIN on its key equalities, with its match
and its other ON conjuncts moved into the WHERE. Every requirement is then a
WHERE conjunct, and the steps split the rows they drop between them: a join
step keeps the rows its table is missing from (its parents present), a
predicate step keeps the rows it fails while every table it reads is
present. So a row a join drops is recovered by the join alone, and any set
of steps of one select can be neutralized together.

The module is pure: it parses and writes SQL and runs nothing.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

DIALECT = "bigquery"
LABEL_CHARS = 160
_VERSION = re.compile(r"\s*FOR SYSTEM_TIME AS OF[^)]*?\)", re.IGNORECASE)
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Step:
    """One place a query can drop a row.

    `id` is `<side>:<scope>:<n>`, where scope is the CTE or subquery the step
    sits in (`main` at the top), prefixed by the table it was found in when
    the trace descended into one; `scope` is that scope. `label` is the scope
    plus the predicate or join text, whitespace collapsed and cut at
    `LABEL_CHARS`. `ordinal` finds the step again in a fresh parse of the same
    SQL.
    """

    id: str
    side: str
    label: str
    kind: str
    ordinal: int
    scope: str = ""


@dataclass(frozen=True)
class TableRef:
    """A base table a query reads where its rows can change the output.

    `wanted` names the columns the query reads from it, or is None when that
    is not known (a `*`).
    """

    dataset: str
    name: str
    wanted: frozenset[str] | None


@dataclass
class _Source:
    alias: str
    node: exp.Expression
    join: exp.Join | None
    side: str  # root, inner, left or other
    present: exp.Expression | None = None
    parents: set[str] = field(default_factory=set)


@dataclass
class _Raw:
    kind: str
    select: exp.Select
    node: exp.Expression | None
    alias: str = ""


def _conjuncts(node: exp.Expression) -> list[exp.Expression]:
    """Split an AND tree, parenthesized ANDs included, into its conjuncts."""
    if isinstance(node, exp.And):
        return _conjuncts(node.left) + _conjuncts(node.right)
    if isinstance(node, exp.Paren) and isinstance(node.this, exp.And):
        return _conjuncts(node.this)
    return [node]


def _own_columns(node: exp.Expression, select: exp.Select) -> list[exp.Column]:
    """Columns under `node` that belong to `select`, not to a nested query."""
    out = []
    for col in node.find_all(exp.Column):
        owner = col.find_ancestor(exp.Select)
        if owner is select:
            out.append(col)
    return out


def _aliases(node: exp.Expression, select: exp.Select, known: set[str]) -> set[str]:
    return {c.table for c in _own_columns(node, select) if c.table in known}


def _text(node: exp.Expression) -> str:
    sql = node.sql(dialect=DIALECT, comments=False)
    return _SPACE.sub(" ", _VERSION.sub("", sql)).strip()


def _source_text(node: exp.Expression) -> str:
    if isinstance(node, exp.Table):
        return ".".join(p for p in (node.db, node.name) if p)
    return "(subquery)"


class _Analysis:
    """Which selects of a query are live, and the steps in each."""

    def __init__(self, tree: exp.Expression, wanted: frozenset[str] | None, first):
        self.tree = tree
        self.first = first
        self.live: dict[int, tuple[exp.Select, frozenset[str] | None]] = {}
        self.tables: list[tuple[exp.Table, frozenset[str] | None]] = []
        self._visit_query(tree, wanted)

    # --- liveness ----------------------------------------------------------

    def _merge(self, a, b):
        if a is None or b is None:
            return None
        return a | b

    def _visit_query(self, node: exp.Expression, wanted) -> None:
        if isinstance(node, exp.Subquery):
            self._visit_query(node.this, wanted)
        elif isinstance(node, exp.SetOperation):
            for branch in (node.this, node.expression):
                if self._null_first(branch, wanted):
                    continue
                self._visit_query(branch, wanted)
        elif isinstance(node, exp.Select):
            self._visit_select(node, wanted)

    def _null_first(self, branch: exp.Expression, wanted) -> bool:
        """A branch that projects the student column as NULL adds no matchable row."""
        if self.first is None or wanted is None or self.first not in wanted:
            return False
        while isinstance(branch, exp.Subquery):
            branch = branch.this
        if not isinstance(branch, exp.Select):
            return False
        for e in branch.expressions:
            if e.alias_or_name == self.first:
                inner = e.unalias()
                while isinstance(inner, exp.Cast):
                    inner = inner.this
                return isinstance(inner, exp.Null)
        return False

    def _visit_select(self, s: exp.Select, wanted) -> None:
        key = id(s)
        if key in self.live:
            old = self.live[key][1]
            merged = self._merge(old, wanted)
            if merged == old:
                return
            wanted = merged
        self.live[key] = (s, wanted)

        sources = _sources(s)
        required = _required(s, sources)
        projections = s.expressions
        if wanted is None:
            wanted_proj = list(projections)
        else:
            wanted_proj = [
                e
                for e in projections
                if isinstance(e, exp.Star)
                or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star))
                or e.alias_or_name in wanted
            ]
        stars = [
            e
            for e in wanted_proj
            if isinstance(e, exp.Star)
            or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star))
        ]

        # Columns read outside the projection list: they decide which rows
        # survive and which match, so a source they name matters.
        rest = []
        for k, v in s.args.items():
            if k in ("expressions", "joins", "from_", "with_"):
                continue
            for item in v if isinstance(v, list) else [v]:
                if isinstance(item, exp.Expression):
                    rest.append(item)
        for j in s.args.get("joins") or []:
            if j.args.get("on") is not None:
                rest.append(j.args["on"])

        def cols(nodes) -> list[exp.Column]:
            out = []
            for n in nodes:
                out += _own_columns(n, s)
            return out

        proj_cols = cols(wanted_proj)
        rest_cols = cols(rest)

        for x in sources:
            if x.side == "other" and not isinstance(x.node, (exp.Table, exp.Subquery)):
                continue
            own_on = x.join.args.get("on") if x.join else None
            other_rest = [
                c for c in rest_cols if own_on is None or not _inside(c, own_on)
            ]
            star_x = any(isinstance(e, exp.Star) or e.table == x.alias for e in stars)
            relevant = (
                x.side in ("root", "inner")
                or x.alias in required
                or wanted is None
                or star_x
                or any(c.table == x.alias for c in proj_cols)
                or any(c.table == x.alias for c in other_rest)
                or (len(sources) == 1)
            )
            if not relevant:
                continue
            # A bare column belongs to the only source; with several it could
            # be any of them, so every source is read whole.
            mine = {x.alias, ""} if len(sources) == 1 else {x.alias}
            bare = len(sources) > 1 and any(not c.table for c in proj_cols + rest_cols)
            if wanted is None or bare or (star_x and len(sources) > 1):
                w = None
            else:
                w = frozenset(c.name for c in proj_cols + rest_cols if c.table in mine)
                if star_x:
                    w |= wanted
            self._visit_source(x.node, w)

        # Subqueries outside the FROM list that decide which rows pass: an
        # IN or EXISTS. A scalar subquery is left alone: neutralizing a step
        # in it can make it return several rows, which BigQuery refuses.
        for n in wanted_proj + rest:
            for sub in n.find_all(exp.Select):
                if sub is s or not _is_predicate(sub):
                    continue
                if sub.find_ancestor(exp.Select) is s or _parent_query(sub) is s:
                    self._visit_select(sub, None)

    def _visit_source(self, node: exp.Expression, wanted) -> None:
        if isinstance(node, exp.Subquery):
            self._visit_query(node.this, wanted)
        elif isinstance(node, exp.Table):
            cte = _cte_for(node)
            if cte is not None:
                self._visit_query(cte.this, wanted)
            elif node.db:
                self.tables.append((node, wanted))

    # --- steps ---------------------------------------------------------------

    def raw_steps(self) -> list[_Raw]:
        out: list[_Raw] = []
        for s in self.tree.find_all(exp.Select):
            if id(s) not in self.live:
                continue
            sources = _sources(s)
            known = {x.alias for x in sources}
            where = s.args.get("where")
            if where is not None:
                out += [
                    _Raw("where", s, c)
                    for c in _conjuncts(where.this)
                    if not _is_row_pick(c, s, sources)
                ]
            required = _required(s, sources)
            for x in sources:
                if x.join is None:
                    continue
                if x.side == "inner" or (x.side == "left" and x.alias in required):
                    out.append(_Raw("join", s, x.join, x.alias))
                    # An INNER JOIN's ON filter drops rows as a WHERE conjunct
                    # would; a LEFT JOIN's only decides what matches.
                    on = x.join.args.get("on")
                    if on is not None and x.side == "inner":
                        out += [
                            _Raw("on", s, c, x.alias)
                            for c in _conjuncts(on)
                            if not _is_key(c, x.alias, s, known)
                            and not _is_row_pick(c, s, sources)
                        ]
            having = s.args.get("having")
            if having is not None:
                out += [_Raw("having", s, c) for c in _conjuncts(having.this)]
        return out


_PICKS = (exp.RowNumber, exp.Rank, exp.DenseRank)
# Where a pick's windows run: each select computing the pick column, and
# its window.
_Windows = list[tuple[exp.Select, exp.Window]]


def _picked_by(source: _Source, name: str) -> bool:
    """`name` is a ROW_NUMBER, RANK or DENSE_RANK column of `source`."""
    return bool(_pick_windows(source, name)[0])


def _pick_windows(source: _Source, name: str, depth: int = 0) -> tuple[_Windows, bool]:
    """Where `source`'s column `name` is computed as a pick window.

    Every branch of a set operation is read. The second value is False when
    some branch computes `name` another way: a pick over it cannot be marked
    in full.
    """
    node = source.node
    if isinstance(node, exp.Table):
        cte = _cte_for(node)
        node = cte.this if cte is not None else None
    found: _Windows = []
    complete = node is not None
    for q in _branches(node) if node is not None else []:
        got, whole = _select_windows(q, name, depth)
        found += got
        complete = complete and whole
    return found, complete


def _select_windows(q: exp.Select, name: str, depth: int) -> tuple[_Windows, bool]:
    """As `_pick_windows`, for one select; a `SELECT *` reads its sources."""
    for e in q.expressions:
        if e.alias_or_name != name:
            continue
        inner = e.unalias()
        if isinstance(inner, exp.Window) and isinstance(inner.this, _PICKS):
            return [(q, inner)], True
        return [], False
    star = any(
        isinstance(e, exp.Star)
        or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star))
        for e in q.expressions
    )
    found: _Windows = []
    complete = True
    if star and depth < 10:
        for x in _sources(q):
            got, whole = _pick_windows(x, name, depth + 1)
            if got:
                found += got
                complete = complete and whole
    return found, bool(found) and complete


def _picks(tree: exp.Expression, live) -> list[tuple[exp.Select, _Windows | None]]:
    """Every live row pick: its select, and where its windows run.

    The windows are None when the pick's column reaches a branch that
    computes it without a window: the pick cannot be marked in full.
    """
    out: list[tuple[exp.Select, _Windows | None]] = []
    for s, _ in live.values():
        sources = _sources(s)
        where = s.args.get("where")
        for c in _conjuncts(where.this) if where is not None else []:
            if not _is_row_pick(c, s, sources):
                continue
            col = c.this if isinstance(c.this, exp.Column) else c.expression
            windows: _Windows = []
            complete = True
            for x in sources:
                if col.table and x.alias != col.table:
                    continue
                got, whole = _pick_windows(x, col.name)
                if got:
                    windows += got
                    complete = complete and whole
            out.append((s, windows if complete else None))
        qualify = s.args.get("qualify")
        if qualify is not None:
            picks = [
                w for w in qualify.find_all(exp.Window) if isinstance(w.this, _PICKS)
            ]
            out.append((s, [(s, w) for w in picks]))
    return out


def _reach(target: exp.Expression) -> Iterator[exp.Select]:
    """Every select under `target`, and under every CTE one of them reads.

    A select in a WHERE (an IN or EXISTS) or a projection counts like one in
    the FROM: a step in it decides which rows `target` keeps.
    """
    seen: set[int] = set()
    todo = [target]
    while todo:
        for q in todo.pop().find_all(exp.Select):
            if id(q) in seen:
                continue
            seen.add(id(q))
            yield q
            for x in _sources(q):
                if isinstance(x.node, exp.Table):
                    cte = _cte_for(x.node)
                    if cte is not None:
                        todo.append(cte.this)


def _feeds(step_select: exp.Select, target: exp.Select) -> bool:
    """`step_select` is `target`, or `target` reads it, however deep."""
    return any(q is step_select for q in _reach(target))


def _reads(target: exp.Select, table: tuple[str, str]) -> bool:
    """`target`, or a query it reads, reads the base table `(dataset, name)`."""
    return any(
        (t.db, t.name) == table and _cte_for(t) is None
        for q in _reach(target)
        for t in q.find_all(exp.Table)
    )


def _mark_picks(
    tree: exp.Expression, live, fed: Callable[[exp.Select], bool], start: int
) -> list[str] | None:
    """Mark each live row pick that `fed` reaches, so `carry` can split by it.

    At each select a reached pick's window runs in, a column `__cand<n>`
    counts the rows of the window's partition.

    Args:
        fed: Whether a select is downstream of what the marks guard against.
        start: The first mark's number.

    Returns:
        The marks, or None when a reached pick cannot be marked in full;
        nothing is marked then.
    """
    todo: dict[int, tuple[exp.Select, exp.Window]] = {}
    for pick_select, windows in _picks(tree, live):
        if windows is None:
            if fed(pick_select):
                return None
            continue
        for select, window in windows:
            if fed(select):
                todo.setdefault(id(window), (select, window))
    marks: list[str] = []
    for select, window in todo.values():
        mark = f"__cand{start + len(marks)}"
        count = exp.Window(
            this=exp.Count(this=exp.Star()),
            partition_by=[p.copy() for p in window.args.get("partition_by") or []],
        )
        select.append("expressions", exp.alias_(count, mark))
        marks.append(mark)
    return marks


def carry(sql: str, marks: list[str]) -> tuple[str, str] | None:
    """Split a variant's rows by how many rows each one's pick could keep.

    Each mark is a `COUNT(*) OVER (PARTITION BY <the pick's partition>)`
    column `relaxed_marked` added where a pick's window runs. It is carried
    up through every query that reads it to the output.

    Returns:
        The rows whose every pick had exactly 1 candidate, and the rest, both
        with the variant's own columns; None when a query on the way (an
        aggregate, a subquery outside FROM, a set operation other than UNION
        ALL, a query inlined twice) cannot carry the count.

    Marks on different branches of a UNION ALL can swap names in its output,
    since each branch adds its NULLs in its own order; the split asks only
    that every mark be 1, so the names do not matter.
    """
    tree = sqlglot.parse_one(sql, dialect=DIALECT)
    for mark in marks:
        starts = [
            q
            for q in tree.find_all(exp.Select)
            if any(e.alias == mark for e in q.expressions)
        ]
        # A query inlined twice holds its mark twice, and one copy's count
        # says nothing about the other's.
        if len(starts) != 1 or not _carry_up(tree, starts[0], mark, 0):
            return None
    body = tree.sql(dialect=DIALECT)
    cols = ", ".join(marks)
    one = " AND ".join(f"COALESCE({m}, 1) = 1" for m in marks)
    # trunk-ignore(bandit/B608): the marks are this module's own column names
    head = f"SELECT * EXCEPT ({cols}) FROM (\n{body}\n) AS __picked WHERE "
    return head + one, head + f"NOT ({one})"


def _projects(q: exp.Select, alias: str, mark: str) -> bool:
    """`q`'s output already holds `mark`, through `*` or by name."""
    for e in q.expressions:
        if isinstance(e, exp.Star) or e.alias_or_name == mark:
            return True
        if isinstance(e, exp.Column) and isinstance(e.this, exp.Star):
            if e.table in ("", alias):
                return True
    return False


def _add(q: exp.Select, alias: str, mark: str) -> bool:
    """Pass `alias.mark` through `q`'s output; False where it cannot go."""
    if _projects(q, alias, mark):
        return True
    if q.args.get("group") is not None or any(
        a.find_ancestor(exp.Window) is None
        for e in q.expressions
        for a in e.find_all(exp.AggFunc)
    ):
        return False
    q.append("expressions", exp.alias_(exp.column(mark, table=alias), mark))
    return True


def _carry_up(tree: exp.Expression, q: exp.Expression, mark: str, depth: int) -> bool:
    """Carry `mark` from query `q`'s output up to the tree's output."""
    if q is tree or depth > 30:
        return q is tree
    parent = q.parent
    while isinstance(parent, exp.Paren):
        parent = parent.parent
    if isinstance(parent, exp.SetOperation):
        top = parent
        while isinstance(top.parent, exp.SetOperation):
            top = top.parent
        # Only UNION ALL keeps every branch's rows whatever column is added.
        # EXCEPT, INTERSECT and UNION DISTINCT compare whole rows, so a mark
        # on one branch alone changes which rows they keep.
        if not all(
            isinstance(op, exp.Union) and not op.args.get("distinct")
            for op in _set_ops(top)
        ):
            return False
        # A UNION matches columns by position: every other branch gets NULL.
        for b in _branches(top):
            if b is not q and not _projects(b, "", mark):
                if not _add_null(b, mark):
                    return False
        return _carry_up(tree, top, mark, depth + 1)
    if isinstance(parent, exp.Subquery):
        if isinstance(parent.parent, exp.SetOperation):
            return _carry_up(tree, parent, mark, depth + 1)
        if isinstance(parent.parent, (exp.From, exp.Join)):
            reader = parent.parent.parent
            if isinstance(reader, exp.Select) and _add(
                reader, parent.alias_or_name, mark
            ):
                return _carry_up(tree, reader, mark, depth + 1)
        return False
    if isinstance(parent, exp.CTE):
        for t in list(tree.find_all(exp.Table)):
            if _cte_for(t) is not parent:
                continue
            reader = (
                t.parent.parent if isinstance(t.parent, (exp.From, exp.Join)) else None
            )
            if not isinstance(reader, exp.Select) or not _add(
                reader, t.alias_or_name, mark
            ):
                return False
            if not _carry_up(tree, reader, mark, depth + 1):
                return False
        return True
    if parent is tree and isinstance(tree, exp.Select):
        return True
    return parent is None


def _branches(node: exp.Expression) -> list[exp.Select]:
    """The selects a query is made of, through set operations and parentheses."""
    out, todo = [], [node]
    while todo:
        n = todo.pop()
        while isinstance(n, (exp.Subquery, exp.Paren)):
            n = n.this
        if isinstance(n, exp.SetOperation):
            todo += [n.this, n.expression]
        elif isinstance(n, exp.Select):
            out.append(n)
    return out


def _set_ops(node: exp.Expression) -> list[exp.SetOperation]:
    """`node` and every set operation nested in its branches."""
    out, todo = [], [node]
    while todo:
        n = todo.pop()
        while isinstance(n, (exp.Subquery, exp.Paren)):
            n = n.this
        if isinstance(n, exp.SetOperation):
            out.append(n)
            todo += [n.this, n.expression]
    return out


def _add_null(q: exp.Select, mark: str) -> bool:
    if q.args.get("group") is not None:
        return False
    q.append("expressions", exp.alias_(exp.cast(exp.null(), "INT64"), mark))
    return True


def _is_row_pick(c: exp.Expression, s: exp.Select, sources: list[_Source]) -> bool:
    """`rn = 1` (or `<= 1`, `< 2`, either way round) on a row-number or rank column."""
    if not isinstance(c, (exp.EQ, exp.LTE, exp.LT, exp.GTE, exp.GT)):
        return False
    col, lit, op = c.this, c.expression, type(c)
    if isinstance(col, exp.Literal):
        # `2 > rn` reads as `rn < 2`.
        flip = {exp.GT: exp.LT, exp.GTE: exp.LTE, exp.LT: exp.GT, exp.LTE: exp.GTE}
        col, lit, op = lit, col, flip.get(op, op)
    if not isinstance(col, exp.Column) or not isinstance(lit, exp.Literal):
        return False
    wanted = {exp.EQ: "1", exp.LTE: "1", exp.LT: "2"}
    if wanted.get(op) != lit.this:
        return False
    owners = [x for x in sources if not col.table or x.alias == col.table]
    return any(_picked_by(x, col.name) for x in owners)


def _is_predicate(sub: exp.Select) -> bool:
    """`sub` is the query of an IN, EXISTS, ANY or ALL, not a scalar value.

    Under NOT, neutralizing a step inside it can only drop more rows.
    """
    p = sub.parent
    while isinstance(p, (exp.Subquery, exp.Paren)):
        p = p.parent
    if not isinstance(p, (exp.In, exp.Exists, exp.Any, exp.All)):
        return False
    up = p.parent
    while isinstance(up, exp.Paren):
        up = up.parent
    return not isinstance(up, exp.Not)


def _inside(node: exp.Expression, ancestor: exp.Expression) -> bool:
    p = node
    while p is not None:
        if p is ancestor:
            return True
        p = p.parent
    return False


def _parent_query(node: exp.Expression) -> exp.Expression | None:
    p = node.parent
    while p is not None and not isinstance(p, (exp.Select, exp.SetOperation)):
        p = p.parent
    return p


def _cte_for(table: exp.Table) -> exp.CTE | None:
    """The CTE a bare table name refers to, from the nearest enclosing WITH."""
    if table.db or table.catalog:
        return None
    name = table.name
    p = table.parent
    while p is not None:
        w = p.args.get("with_") if isinstance(p, exp.Expression) else None
        if isinstance(w, exp.With):
            for cte in w.expressions:
                if cte.alias == name and not _inside(table, cte):
                    return cte
                if cte.alias == name and _inside(table, cte):
                    break
        p = p.parent
    return None


def _sources(s: exp.Select) -> list[_Source]:
    """The FROM source and each join of `s`, with how each can drop rows."""
    out: list[_Source] = []
    root = s.args.get("from_")
    if root is not None:
        node = root.this
        out.append(_Source(node.alias_or_name, node, None, "root"))
    for j in s.args.get("joins") or []:
        node = j.this
        alias = node.alias_or_name
        side = (j.side or "").upper()
        kind = (j.kind or "").upper()
        on = j.args.get("on")
        if isinstance(node, exp.Unnest) or on is None or j.args.get("using"):
            how = "other"
        elif side == "LEFT":
            how = "left"
        elif side == "" and kind in ("", "INNER"):
            how = "inner"
        else:
            how = "other"
        out.append(_Source(alias, node, j, how))
    known = {x.alias for x in out}
    joined = {x.alias for x in out if x.side in ("inner", "left")}
    for x in out:
        on = x.join.args.get("on") if x.join else None
        if on is None or x.side not in ("inner", "left"):
            continue
        # With no key equality, the alias itself: an unmatched LEFT JOIN row
        # reads as NULL.
        x.present = _present(on, x.alias, s, known) or exp.column(x.alias)
        x.parents = _aliases(on, s, known) & joined - {x.alias}
    return out


def _present(on: exp.Expression, alias: str, s: exp.Select, known: set[str]):
    """A column of `alias` a key equality makes non-null on every matched row.

    Only an equality with another source counts: a filter column such as
    `x.status = 'on'` would make its own NULLs read as a missing match.
    """
    for c in _conjuncts(on):
        if not isinstance(c, exp.EQ):
            continue
        for mine, theirs in ((c.this, c.expression), (c.expression, c.this)):
            others = _aliases(theirs, s, known)
            if (
                isinstance(mine, exp.Column)
                and mine.table == alias
                and others
                and alias not in others
            ):
                return mine
    return None


def _is_key(c: exp.Expression, alias: str, s: exp.Select, known: set[str]) -> bool:
    """An ON equality between `alias` and another source: a join key, not a filter."""
    if not isinstance(c, exp.EQ):
        return False
    left = _aliases(c.this, s, known)
    right = _aliases(c.expression, s, known)
    return bool(left and right) and bool(
        (alias in left and alias not in right and right - {alias})
        or (alias in right and alias not in left and left - {alias})
    )


def _ancestors(alias: str, by_alias: dict[str, _Source]) -> list[str]:
    out: list[str] = []
    todo = list(by_alias[alias].parents) if alias in by_alias else []
    while todo:
        a = todo.pop()
        if a in out or a == alias:
            continue
        out.append(a)
        todo += list(by_alias[a].parents) if a in by_alias else []
    return sorted(out)


def _chain(aliases: set[str], by_alias: dict[str, _Source]) -> set[str]:
    """`aliases` that are joined and could be missing, with the joins they hang on."""
    out: set[str] = set()
    for a in aliases:
        x = by_alias.get(a)
        if x is None or x.side not in ("inner", "left"):
            continue
        out.add(a)
        out |= set(_ancestors(a, by_alias))
    return {a for a in out if by_alias[a].side in ("inner", "left")}


def _requirements(s: exp.Select, sources: list[_Source]):
    """Each WHERE conjunct, and each INNER JOIN's own match, with its chain."""
    by_alias = {x.alias: x for x in sources}
    known = set(by_alias)
    out = []
    where = s.args.get("where")
    if where is not None:
        for c in _conjuncts(where.this):
            out.append((c, _chain(_aliases(c, s, known), by_alias)))
    for x in sources:
        if x.side == "inner":
            out.append((x, _chain({x.alias}, by_alias)))
    return out


def _required(s: exp.Select, sources: list[_Source]) -> set[str]:
    """Aliases whose absence drops a row: the chain of any requirement."""
    out: set[str] = set()
    for _, chain in _requirements(s, sources):
        out |= chain
    return {a for a in out if any(x.alias == a and x.side == "left" for x in sources)}


def _is_absent(x: _Source) -> exp.Expression:
    """`x` matched no row: its match marker is NULL."""
    marker = x.present.copy() if x.present is not None else exp.column(x.alias)
    return exp.Is(this=marker, expression=exp.Null())


def _is_present(x: _Source) -> exp.Expression:
    return exp.not_(_is_absent(x))


def _all_present(aliases, by_alias: dict[str, _Source]) -> exp.Expression | None:
    conds = [_is_present(by_alias[a]) for a in sorted(aliases) if a in by_alias]
    if not conds:
        return None
    return exp.and_(*conds) if len(conds) > 1 else conds[0]


def _scope(node: exp.Expression) -> str:
    p = node.parent
    while p is not None:
        if isinstance(p, exp.CTE):
            return p.alias
        if isinstance(p, exp.Subquery) and p.alias:
            return p.alias
        p = p.parent
    return "main"


def _label(raw: _Raw) -> str:
    if isinstance(raw.node, exp.Join):
        how = "INNER" if not raw.node.side else raw.node.side.upper()
        text = f"{how} JOIN {_source_text(raw.node.this)} AS {raw.alias}"
        on = raw.node.args.get("on")
        if on is not None:
            text += f" ON {_text(on)}"
        return text
    text = _text(raw.node) if raw.node is not None else ""
    if raw.kind == "on":
        return f"{text} (ON {raw.alias})"
    if raw.kind == "having":
        return f"HAVING {text}"
    return text


class Query:
    """A parsed query whose steps can be listed and neutralized one at a time.

    Args:
        sql: BigQuery SQL, typically already read as of a moment.
        wanted: The output columns that identify a row (the comparison's
            grain), or None to treat every column as one.
        first: The grain's student column: a UNION branch that projects it
            as NULL is pruned.
    """

    def __init__(
        self,
        sql: str,
        wanted: frozenset[str] | None = None,
        first: str | None = None,
    ) -> None:
        self._tree = sqlglot.parse_one(sql, dialect=DIALECT)
        self._wanted = wanted
        self._first = first

    def sql(self) -> str:
        """The query regenerated unchanged, as every relaxed variant is."""
        return self._tree.sql(dialect=DIALECT)

    def _analysis(self, tree: exp.Expression) -> _Analysis:
        return _Analysis(tree, self._wanted, self._first)

    def steps(self, side: str, prefix: str = "") -> list[Step]:
        """List the live steps, in a stable order.

        Args:
            side: `dashboard` or `cube`, the first part of each id.
            prefix: The table the steps were found in, for a descended level.
        """
        out = []
        counts: dict[str, int] = {}
        for i, raw in enumerate(self._analysis(self._tree).raw_steps()):
            node = raw.node if raw.node is not None else raw.select
            scope = _scope(node if raw.kind != "join" else raw.select)
            if prefix:
                scope = f"{prefix}/{scope}"
            counts[scope] = counts.get(scope, 0) + 1
            label = f"{scope}: {_label(raw)}"
            if len(label) > LABEL_CHARS:
                label = label[: LABEL_CHARS - 1] + "…"
            out.append(
                Step(f"{side}:{scope}:{counts[scope]}", side, label, raw.kind, i, scope)
            )
        return out

    def tables(self) -> list[TableRef]:
        """The live base tables this query reads, merged by name."""
        merged: dict[tuple[str, str], frozenset[str] | None] = {}
        seen: set[tuple[str, str]] = set()
        for node, wanted in self._analysis(self._tree).tables:
            key = (node.db, node.name)
            if key in seen:
                old = merged[key]
                merged[key] = None if old is None or wanted is None else old | wanted
            else:
                seen.add(key)
                merged[key] = wanted
        return [TableRef(ds, name, w) for (ds, name), w in merged.items()]

    def relaxed(self, step: Step) -> str:
        """The query with `step` neutralized, every other step kept."""
        return self.relaxed_many([step])

    def _chosen(
        self, tree: exp.Expression, steps: list[Step], analysis: _Analysis | None = None
    ) -> list[_Raw]:
        raws = (analysis or self._analysis(tree)).raw_steps()
        return [raws[s.ordinal] for s in steps]

    def relaxed_many(self, steps: list[Step]) -> str:
        """The query with every one of `steps` neutralized together."""
        tree = self._tree.copy()
        _neutralize(self._chosen(tree, steps))
        return tree.sql(dialect=DIALECT)

    def relaxed_marked(
        self, steps: list[Step], start: int = 0
    ) -> tuple[str, list[str] | None]:
        """`relaxed_many`, with each row pick downstream of a step marked.

        A neutralized step upstream of a pick can let another row win it. So
        where each such pick's window runs, a column `__cand<n>`, numbered
        from `start`, counts the rows in its partition; `carry` splits the
        rows by it. A step is upstream of a pick when the pick's window
        select reads the step's select, however deep: in its FROM, in an IN
        or EXISTS of its WHERE, or through CTEs.

        Returns:
            The SQL, and the marks it carries: none when no pick follows a
            step, or None when one does but cannot be marked in full (a
            branch of a set operation computes the pick's column without a
            window). The SQL is then `relaxed_many`'s.
        """
        tree = self._tree.copy()
        analysis = self._analysis(tree)
        chosen = self._chosen(tree, steps, analysis)
        selects = [r.select for r in chosen]
        marks = _mark_picks(
            tree,
            analysis.live,
            lambda target: any(_feeds(s, target) for s in selects),
            start,
        )
        _neutralize(chosen)
        return tree.sql(dialect=DIALECT), marks

    def inline_marked(
        self, replacements: dict[tuple[str, str], str], start: int = 0
    ) -> tuple[str, list[str] | None]:
        """`inline`, with each row pick downstream of a replaced table marked.

        The marks are as `relaxed_marked` makes them, numbered from `start`:
        a step inside the replaced table's SQL can let another row win a
        pick here.

        Returns:
            The SQL, and the marks: none when no pick reads a replaced table,
            or None when one does but cannot be marked in full. The SQL is
            then `inline`'s.
        """
        tree = self._tree.copy()
        live = self._analysis(tree).live
        marks = _mark_picks(
            tree,
            live,
            lambda target: any(_reads(target, key) for key in replacements),
            start,
        )
        return _inline(tree, replacements).sql(dialect=DIALECT), marks

    def relaxed_all(
        self,
        replacements: dict[tuple[str, str], str] | None = None,
        picks: bool = True,
    ) -> str:
        """The query with every live step neutralized at once.

        With `picks`, row picks (QUALIFY, `rn = 1`) are dropped too: they are
        never a cause, but a row they drop is still in the tables. So a row
        this does not return is missing from the tables the query reads.
        Without, the picks stay, and a row this does not return is missing
        or dropped by a pick.

        Args:
            replacements: Tables to read as these subqueries instead, as
                `inline` takes them.
            picks: Drop the row picks as well.
        """
        tree = self._tree.copy()
        analysis = self._analysis(tree)
        picked = []
        for s, _ in analysis.live.values() if picks else []:
            sources = _sources(s)
            where = s.args.get("where")
            if where is not None:
                picked += [
                    c for c in _conjuncts(where.this) if _is_row_pick(c, s, sources)
                ]
            if s.args.get("qualify") is not None:
                s.set("qualify", None)
        for raw in analysis.raw_steps():
            if isinstance(raw.node, exp.Join):
                if not raw.node.side:
                    _as_left(raw.node)
            elif raw.node is not None and raw.node.parent is not None:
                raw.node.replace(exp.true())
        for c in picked:
            if c.parent is not None:
                c.replace(exp.true())
        return _inline(tree, replacements or {}).sql(dialect=DIALECT)

    def inline(self, replacements: dict[tuple[str, str], str]) -> str:
        """The query with each `(dataset, table)` read replaced by a subquery."""
        return _inline(self._tree.copy(), replacements).sql(dialect=DIALECT)


def _inline(
    tree: exp.Expression, replacements: dict[tuple[str, str], str]
) -> exp.Expression:
    for node in list(tree.find_all(exp.Table)):
        key = (node.db, node.name)
        if key not in replacements or _cte_for(node) is not None:
            continue
        body = sqlglot.parse_one(replacements[key], dialect=DIALECT)
        alias = node.alias or node.name
        node.replace(
            exp.Subquery(this=body, alias=exp.TableAlias(this=exp.to_identifier(alias)))
        )
    return tree


def _as_left(join: exp.Join | None) -> None:
    """Read an INNER JOIN as a LEFT JOIN."""
    if join is not None:
        join.set("side", "LEFT")
        join.set("kind", None)


def _canonicalize(s: exp.Select) -> dict[int, exp.Expression]:
    """Rewrite `s` to an equal query whose every requirement is a WHERE conjunct.

    Each INNER JOIN becomes a LEFT JOIN on its key equalities; its other ON
    conjuncts and its own match (`<marker> IS NOT NULL`) move into the WHERE.
    A LEFT JOIN on the keys keeps every pair the keys allow, and the moved
    conjuncts then drop the same pairs, and the same unmatched rows, the
    INNER JOIN did.

    Returns:
        Each moved ON conjunct's new WHERE node, by the id of the old one.
    """
    sources = _sources(s)
    known = {x.alias for x in sources}
    moved: dict[int, exp.Expression] = {}
    added: list[exp.Expression] = []
    for x in sources:
        if x.side != "inner" or x.join is None:
            continue
        on = x.join.args.get("on")
        conjuncts = _conjuncts(on) if on is not None else []
        keys = [c for c in conjuncts if _is_key(c, x.alias, s, known)]
        for c in conjuncts:
            if any(c is k for k in keys):
                continue
            new = c.copy()
            moved[id(c)] = new
            added.append(new)
        added.append(_is_present(x))
        x.join.set("on", exp.and_(*[k.copy() for k in keys]) if keys else exp.true())
        _as_left(x.join)
    for cond in added:
        s.where(cond, copy=False)
    return moved


def _neutralize(raws: list[_Raw]) -> None:
    """Neutralize `raws` together, select by select, in canonical form."""
    by_select: dict[int, list[_Raw]] = {}
    for raw in raws:
        by_select.setdefault(id(raw.select), []).append(raw)

    def depth(group: list[_Raw]) -> int:
        n, p = 0, group[0].select.parent
        while p is not None:
            n += isinstance(p, exp.Select)
            p = p.parent
        return n

    # Inner selects first: an outer step rewrites the conjunct that holds
    # them through a copy, which would leave their own edit behind.
    for group in sorted(by_select.values(), key=depth, reverse=True):
        s = group[0].select
        moved = _canonicalize(s)
        sources = _sources(s)
        by_alias = {x.alias: x for x in sources}
        known = set(by_alias)

        # Predicates first: a join step rewrites the conjuncts around them.
        for raw in group:
            if raw.kind == "join" or raw.node is None:
                continue
            node = moved.get(id(raw.node), raw.node)
            if node.parent is None:
                continue
            if raw.kind == "having":
                node.replace(exp.true())
                continue
            cond = _all_present(_chain(_aliases(node, s, known), by_alias), by_alias)
            if cond is None:
                node.replace(exp.true())
            else:
                # Parenthesized, or the OR swallows the AND chain it sits in.
                node.replace(exp.paren(exp.or_(exp.paren(node.copy()), cond)))

        # A join: the rows its table is missing from pass every requirement
        # that hangs on it, as long as the joins it hangs on are present.
        for raw in group:
            if raw.kind != "join" or raw.alias not in by_alias:
                continue
            x = by_alias[raw.alias]
            hangs_on = _all_present(_ancestors(x.alias, by_alias), by_alias)
            missing = (
                _is_absent(x) if hangs_on is None else exp.and_(_is_absent(x), hangs_on)
            )
            where = s.args.get("where")
            for req in _conjuncts(where.this) if where is not None else []:
                if x.alias in _chain(_aliases(req, s, known), by_alias):
                    req.replace(
                        exp.paren(
                            exp.or_(exp.paren(req.copy()), exp.paren(missing.copy()))
                        )
                    )
