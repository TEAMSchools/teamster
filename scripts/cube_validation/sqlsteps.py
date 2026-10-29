"""Find the steps of a query that can drop a row, and neutralize one at a time.

A step is one place a query can drop a row: a WHERE, HAVING or QUALIFY
conjunct, an INNER JOIN, a LEFT JOIN a later predicate requires, or an
INNER JOIN's ON conjunct other than a key equality (which filters as a WHERE
conjunct would). Steps are found in every SELECT, CTE,
subquery and inlined view that can change which rows the query returns;
the rest (a CTE nothing reads, a LEFT JOIN that feeds no output key and
nothing requires, a UNION branch whose student column is NULL) are pruned.

A required LEFT JOIN and the predicates that require it split the rows they
drop between them: neutralizing the join keeps the rows its table is missing
from, neutralizing a predicate keeps the rows it fails while every table it
reads is present. So a row the join drops is recovered by the join alone,
not by the join and its predicate both.

The module is pure: it parses and writes SQL and runs nothing.
"""

from __future__ import annotations

import re
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
    the trace descended into one. `label` is the scope plus the predicate or
    join text, whitespace collapsed and cut at `LABEL_CHARS`. `ordinal`
    finds the step again in a fresh parse of the same SQL.
    """

    id: str
    side: str
    label: str
    kind: str
    ordinal: int


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
    present: exp.Column | None = None
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

        # Subqueries outside the FROM list: in a wanted projection or a filter.
        for n in wanted_proj + rest:
            for sub in n.find_all(exp.Select):
                if sub is s:
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
                out += [_Raw("where", s, c) for c in _conjuncts(where.this)]
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
                        ]
            for clause in ("having", "qualify"):
                node = s.args.get(clause)
                if node is not None:
                    out += [_Raw(clause, s, c) for c in _conjuncts(node.this)]
        return out


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
        x.present = _present(on, x.alias, s, known)
        x.parents = _aliases(on, s, known) & joined - {x.alias}
    return out


def _present(on: exp.Expression, alias: str, s: exp.Select, known: set[str]):
    """A column of `alias` an ON equality makes non-null on every matched row."""
    for c in _conjuncts(on):
        if not isinstance(c, exp.EQ):
            continue
        for mine, theirs in ((c.this, c.expression), (c.expression, c.this)):
            if (
                isinstance(mine, exp.Column)
                and mine.table == alias
                and alias not in _aliases(theirs, s, known)
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
    """`x`'s match column is NULL; only called for a source that has one."""
    return exp.Is(
        this=x.present.copy() if x.present else exp.null(), expression=exp.Null()
    )


def _is_present(x: _Source) -> exp.Expression:
    return exp.not_(_is_absent(x))


def _all_present(aliases, by_alias: dict[str, _Source]) -> exp.Expression | None:
    conds = [
        _is_present(by_alias[a])
        for a in sorted(aliases)
        if by_alias[a].present is not None
    ]
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
    if raw.kind in ("having", "qualify"):
        return f"{raw.kind.upper()} {text}"
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
                Step(f"{side}:{scope}:{counts[scope]}", side, label, raw.kind, i)
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
        tree = self._tree.copy()
        raws = self._analysis(tree).raw_steps()
        raw = raws[step.ordinal]
        _neutralize(raw)
        return tree.sql(dialect=DIALECT)

    def relaxed_all(
        self, replacements: dict[tuple[str, str], str] | None = None
    ) -> str:
        """The query with every live step neutralized at once.

        It keeps at least the rows any single neutralized step keeps, short
        of an anti-join or a row pick that more rows can change, so a row it
        does not return is one no step of this query recovers.

        Args:
            replacements: Tables to read as these subqueries instead, as
                `inline` takes them.
        """
        tree = self._tree.copy()
        for raw in self._analysis(tree).raw_steps():
            if isinstance(raw.node, exp.Join):
                if not raw.node.side:
                    _as_left(raw.node)
            elif raw.node is not None and raw.node.parent is not None:
                raw.node.replace(exp.true())
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


def _neutralize(raw: _Raw) -> None:
    s = raw.select
    sources = _sources(s)
    by_alias = {x.alias: x for x in sources}

    if raw.node is None:
        return

    if raw.kind in ("having", "qualify", "on"):
        raw.node.replace(exp.true())
        return

    if raw.kind == "where":
        chain = _chain(_aliases(raw.node, s, set(by_alias)), by_alias)
        cond = _all_present(chain, by_alias)
        if cond is None:
            raw.node.replace(exp.true())
        else:
            raw.node.replace(exp.or_(exp.paren(raw.node.copy()), cond))
        return

    # A join: the rows its table is missing from pass every requirement that
    # hangs on it, as long as the joins it hangs on are present.
    x = by_alias[raw.alias]
    if x.present is None:
        if x.side == "inner":
            _as_left(x.join)
        return
    hangs_on = _all_present(_ancestors(x.alias, by_alias), by_alias)
    missing = _is_absent(x) if hangs_on is None else exp.and_(_is_absent(x), hangs_on)

    added: list[exp.Expression] = []
    for req, chain in _requirements(s, sources):
        if isinstance(req, _Source):
            if req.present is None:
                continue
            # An INNER JOIN read as a LEFT JOIN that requires its match.
            _as_left(req.join)
            if req is x:
                # Its own match is required only of rows the joins it hangs
                # on reach.
                if hangs_on is not None:
                    added.append(exp.or_(_is_present(x), exp.paren(hangs_on.copy())))
                continue
            cond = _is_present(req)
            if x.alias in chain:
                cond = exp.or_(cond, exp.paren(missing.copy()))
            added.append(cond)
        elif x.alias in chain:
            req.replace(exp.or_(exp.paren(req.copy()), exp.paren(missing.copy())))
    for cond in added:
        s.where(cond, copy=False)
