"""Analyst decisions: who fixes a formula gap, applied to the cells it explains."""

from __future__ import annotations

from dataclasses import replace

from . import cells as cells_mod
from .cells import Cell
from .config import Checks, Decision, param_matches
from .probes import ProbeResult

_VERDICT = {
    "dashboard": cells_mod.FIX_DASHBOARD,
    "cube": cells_mod.FIX_CUBE,
    "accepted": cells_mod.ACCEPTED,
}


def _key(cut: str, sheet: str, dims: dict[str, str]) -> tuple:
    return (cut, sheet, tuple(sorted(dims.items())))


def _applies(d: Decision, cell: Cell, params: dict[str, str]) -> bool:
    if cell.measure != d.measure:
        return False
    return param_matches(d.param, params)


def _label(d: Decision) -> str:
    param = f" / {d.param[0]} = {d.param[1]}" if d.param else ""
    return f"{d.measure}{param} ({d.owner})"


def apply(
    checks: Checks, cells: list[Cell], probes: list[ProbeResult]
) -> tuple[list[Cell], list[dict]]:
    """Relabel the formula-gap cells each decision explains.

    A dashboard or cube decision relabels a cell only when its probe is proven
    and the probe's candidate matches Cube on that cell. An accepted decision
    relabels the cells in its cuts or sheets. Row gaps are never relabeled. A
    passing cell counts as resolved under the same test: its candidate matches
    Cube (dashboard, cube), or it is in scope (accepted).

    Args:
        checks: The dashboard's checks file.
        cells: The judged cells.
        probes: The probe results, matched to decisions by probe id.

    Returns:
        The cells in their original order, and one summary per decision.
    """
    params = {c.id: c.params for c in checks.cuts}
    by_probe = {p.probe: p for p in probes}
    out = list(cells)
    summaries = []
    for d in checks.decisions:
        result = by_probe.get(d.probe) if d.probe else None
        proven = bool(result and result.proven)
        matches = {
            _key(p.cut, p.sheet, p.dims)
            for p in (result.cells if result else [])
            if p.candidate_matches_cube
        }
        relabeled = still = resolved = 0
        for i, c in enumerate(out):
            if c.cut not in params or not _applies(d, c, params[c.cut]):
                continue
            explained = proven and _key(c.cut, c.sheet, c.dims) in matches
            if c.verdict == cells_mod.PASS:
                # only a pass the rule explains is resolved, not one that always passed
                resolved += _in_scope(d, c) if d.owner == "accepted" else explained
                continue
            if c.verdict != cells_mod.FORMULA_GAP:
                continue
            if d.owner == "accepted":
                hit = _in_scope(d, c)
            else:
                hit = explained
            if hit:
                out[i] = replace(c, verdict=_VERDICT[d.owner], reason=d.rule)
                relabeled += 1
            elif d.owner != "accepted" or _in_scope(d, c):
                still += 1
        summaries.append(
            {
                "decision": _label(d),
                "owner": d.owner,
                "relabeled": relabeled,
                "still_formula_gap": still,
                "resolved": resolved,
                "probe_proven": proven,
            }
        )
    return out, summaries


def _in_scope(d: Decision, cell: Cell) -> bool:
    return cell.cut in d.cuts or cell.sheet in d.sheets
