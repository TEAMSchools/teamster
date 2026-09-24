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
    # Split on commas, not on a capitalised-word regex. A regex breaks
    # "Delle Donne" and "Diggins-Smith" into pieces and does not match
    # Dončić or Şengün at all, so it would silently compare the wrong set.
    #
    # Take the text after the LAST colon, not the first: the prose above the
    # list may contain one, and splitting on the first swallowed a sentence
    # into the name set. Collapse whitespace too, because the list is
    # line-wrapped and a name can straddle the break.
    listed = block.rsplit(":", 1)[1].strip().rstrip(".")
    listed = re.sub(r"\s+", " ", listed)
    return {part.strip() for part in listed.split(",") if part.strip()}


def test_the_page_publishes_exactly_the_reserved_surnames() -> None:
    declared = set(yaml.safe_load(_NAMES.read_text(encoding="utf-8"))["surnames"])
    assert declared
    assert _published() == declared


def test_the_reservation_is_not_silently_empty() -> None:
    # A parser change that made _published() return nothing would make the
    # test above pass only if the YAML were empty too — assert the real size
    # so neither can quietly become a no-op.
    assert len(_published()) == 59
