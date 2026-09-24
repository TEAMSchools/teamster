"""The published reservation must match the file it reserves.

Publishing the list is what makes the namespace reserved, so a surname the
YAML carries but the page does not is a name nobody outside the repo has been
told about — reserved in name only. A surname the page carries but the YAML
does not is worse: it is a word this repo has told people not to use and no
longer uses itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).parents[2]
_NAMES = _ROOT / "src" / "cube" / "sandbox" / "reserved_names.yml"
_PAGE = _ROOT / "docs" / "reference" / "cube-sandbox.md"


def _published() -> set[str]:
    """The surnames named in the page's reservation admonition."""
    text = _PAGE.read_text(encoding="utf-8")
    start = text.index("must not be used for anything else")
    block = text[start : text.index("Given names stay realistic", start)]
    return set(re.findall(r"\b[A-Z][a-z]+\b", block.split(":", 1)[1]))


def test_the_page_publishes_exactly_the_reserved_surnames() -> None:
    declared = set(yaml.safe_load(_NAMES.read_text(encoding="utf-8"))["surnames"])
    assert declared
    assert _published() == declared


def test_the_reservation_is_not_silently_empty() -> None:
    # A parser change that made _published() return nothing would make the
    # test above pass only if the YAML were empty too — assert the real size
    # so neither can quietly become a no-op.
    assert len(_published()) == 40
