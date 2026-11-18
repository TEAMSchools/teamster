import sys
from datetime import datetime, timezone

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import trace

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.answers import HandCheck, _check_json

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import mask, suppress

START = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def mask_below_15(monkeypatch):
    """Raise `MASK_BELOW` to 15 in every module that imported it.

    Patching each binding, not only `report`'s, means a module that compares
    against `MASK_BELOW` is covered, and a module that hardcodes 10 is caught.
    """
    for name, module in list(sys.modules.items()):
        if name.startswith("cube_validation") and hasattr(module, "MASK_BELOW"):
            monkeypatch.setattr(module, "MASK_BELOW", 15)


def test_every_mask_and_label_follows_mask_below(mask_below_15):
    assert mask(14) == "<15" and mask(15) == "15"
    assert suppress(25, [14, 11]) == ("masked", ["<15", "<15"])


def test_a_posted_trace_masks_and_labels_by_mask_below(mask_below_15):
    found = trace.ItemTrace("dashboard", 25)
    found.steps["s"] = 5
    found.labels["s"] = "main: s"
    found.many = 12
    found.many_labels = ["a", "b"]
    found.none = 8

    lines = found.evidence(posted=True)

    assert lines[0] == "main: s: <15 rows"
    assert lines[1].startswith("masked rows unattributed: ")
    # Both reasons sit under 15, so both read `<15`; none reads `<10`.
    assert lines[1].count("<15 ") == 2
    assert "<10" not in " ".join(lines)
    assert "12" not in lines[1] and " 8 " not in lines[1]


def test_a_hand_check_masks_and_labels_by_mask_below(mask_below_15):
    check = HandCheck(
        "enrollment", "{}", (), 12.0, 300.0, "", "", 0.0, 0.0, START, False
    )
    posted = _check_json("v", check)
    assert (posted["dashboard"], posted["cube"]) == ("<15", "300")

    # Two counts 12 apart would post a difference under 15.
    close = HandCheck(
        "enrollment", "{}", (), 120.0, 132.0, "", "", 0.0, 0.0, START, False
    )
    posted = _check_json("v", close)
    assert (posted["dashboard"], posted["cube"]) == ("<masked>", "<masked>")
