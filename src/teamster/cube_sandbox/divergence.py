"""Assert that queries a careless kit treats as equivalent are not.

Separate from canaries.yml: a canary going red means the access model broke,
this going red means KTAF's generator regressed. MasterBorn runs the canaries
as their gate and cannot fix this one, and a gate that fails for something the
person holding it cannot fix is how a gate starts getting overridden. One
runner serves both.

Each pair compiles, runs, and returns a plausible wrong number. The fabricated
data has to make each one visibly wrong, or the sandbox teaches that the
careless form is fine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DIVERGENCES_PATH = Path("src/cube/sandbox/divergences.yml")


@dataclass(frozen=True)
class Divergence:
    name: str
    min_ratio: float
    why: str
    a: str
    b: str


def diverges(a: float, b: float, min_ratio: float) -> bool:
    """Whether two results differ by at least min_ratio of the larger.

    Relative to the LARGER of the two, so the ratio means the same thing in
    both directions. Two zeros are equal, not infinitely different, and
    dividing would raise.
    """
    if not a and not b:
        return False
    return abs(a - b) / max(abs(a), abs(b)) >= min_ratio


def load(path: Path = DIVERGENCES_PATH) -> list[Divergence]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = [Divergence(**entry) for entry in doc.get("divergences", [])]
    if not out:
        raise ValueError(f"{path} declares no divergences")
    for item in out:
        if not 0 < item.min_ratio < 1:
            raise ValueError(
                f"{item.name}: min_ratio must be between 0 and 1, got "
                f"{item.min_ratio}. A ratio of 0 passes on any pair at all."
            )
    return out


def assess(
    divergences: list[Divergence], results: dict[str, tuple[float, float]]
) -> list[dict[str, Any]]:
    """Score each declared divergence against its measured pair."""
    out = []
    for item in divergences:
        pair = results.get(item.name)
        if pair is None:
            out.append({"name": item.name, "status": "unproven", "detail": "not run"})
            continue
        a, b = pair
        held = diverges(a, b, item.min_ratio)
        out.append(
            {
                "name": item.name,
                "status": "held" if held else "converged",
                "detail": f"a={a}, b={b}, min_ratio={item.min_ratio}",
            }
        )
    return out


def exit_code(assessed: list[dict[str, Any]]) -> int:
    # Converged and unproven both fail. A pair that did not run has not shown
    # the lesson any more than one that converged.
    return 1 if any(r["status"] != "held" for r in assessed) else 0
