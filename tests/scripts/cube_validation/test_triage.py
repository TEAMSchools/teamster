from datetime import datetime, timezone

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import CellDiff, Gap, Group
from cube_validation.config import ColumnPair, Comparison, Proof, ViewConfig
from cube_validation.cube_client import MemberDoc
from cube_validation.decisions import Applied
from cube_validation.moment import Build
from cube_validation.report import RunResult
from cube_validation.triage import SUGGESTIONS, open_items, suggest

START = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 27, 6, 5, tzinfo=timezone.utc)


def _proof(**kw):
    return Proof(fingerprint="f", cells=None, proven_at="2026-10-27", **kw)


def _cfg(**proof_kw):
    cmp = Comparison(
        id="enrollment",
        measure="student_count",
        dims=[ColumnPair("Grade", "grade_level")],
        proof=_proof(**proof_kw),
    )
    return ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])


def _run(groups=(), gaps=(), cells=()):
    return RunResult(
        view="enrollment",
        moment=Build(start=START, end=END, job_id="j"),
        measures=[],
        applied=Applied(
            open=list(groups), open_gaps=list(gaps), open_cells=list(cells)
        ),
    )


def _gap(field="Enroll Status", kind="filter"):
    return Gap(kind, field, ("Roster",), ("enrollment",), restricting=False)


def _doc(name, description="", ai_context="", title=""):
    return MemberDoc(name, title, description, ai_context, "dimension")


def test_unrestricting_filter_suggests_filters_nothing():
    cfg = _cfg(restricting_filters=[])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "filters_nothing"
    assert s.evidence == ("keeps every member on Roster",)


def test_copy_note_suggests_filters_nothing():
    cfg = _cfg(
        restricting_filters=["Enroll Status"],
        filter_notes={"Enroll Status": "copy of Grade"},
    )

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "filters_nothing"
    assert s.evidence == ("copy of Grade",)


def test_caption_match_lists_candidates_without_value_check():
    cfg = _cfg(restricting_filters=["Grade Level"])
    docs = {"grade_level": _doc("grade_level"), "region": _doc("region")}

    [s] = suggest(cfg, _run(gaps=[_gap("Grade Level")]), docs)

    assert s.suggestion == "owner"
    assert s.candidates == ("grade_level",)


def test_same_values_suggests_map_filters():
    cfg = _cfg(restricting_filters=["Grade Level"])
    docs = {"grade_level": _doc("grade_level")}
    seen = []

    def values(caption, member):
        seen.append((caption, member))
        return "same values on 9 of 9"

    [s] = suggest(cfg, _run(gaps=[_gap("Grade Level")]), docs, values)

    assert seen == [("Grade Level", "grade_level")]
    assert s.suggestion == "map_filters"
    assert s.candidates == ("grade_level",)
    assert s.evidence == ("grade_level: same values on 9 of 9",)


def test_different_values_do_not_map_filters():
    cfg = _cfg(restricting_filters=["Grade Level"])
    docs = {"grade_level": _doc("grade_level")}

    [s] = suggest(
        cfg, _run(gaps=[_gap("Grade Level")]), docs, lambda c, m: "differ on 2"
    )

    assert s.suggestion == "owner"
    assert s.candidates == ("grade_level",)


def test_member_docs_suggest_docs_with_quoted_evidence():
    cfg = _cfg()
    docs = {
        "student_count": _doc("student_count", description="Counts enrolled students."),
        "grade_level": _doc("grade_level", ai_context="Use for the grade filter."),
    }
    group = Group("enrollment", (("grade_level", "9"),), "value_differs", 40, 38)

    [s] = suggest(cfg, _run(groups=[group]), docs)

    assert s.suggestion == "docs"
    assert s.evidence == (
        "student_count: Counts enrolled students.",
        "grade_level: Use for the grade filter.",
    )


def test_nothing_found_goes_to_owner_last():
    cfg = _cfg(restricting_filters=["Odd Field"])
    cells = CellDiff("enrollment", {"differs": 3})
    result = suggest(
        cfg, _run(gaps=[_gap("Odd Field"), _gap("Enroll Status")], cells=[cells]), {}
    )

    names = [s.suggestion for s in result]
    assert names == ["filters_nothing", "owner", "owner"]
    assert names == sorted(names, key=SUGGESTIONS.index)
    assert result[-1].evidence == ("no description or ai_context answers it",)
    assert SUGGESTIONS == ("map_filters", "filters_nothing", "docs", "owner")


def test_item_ids_are_stable_and_hold_no_unreviewed_value():
    shown = Group("enrollment", (("grade_level", "9"),), "value_differs", 40, 38)
    small = Group("enrollment", (("grade_level", "9"),), "value_differs", 4, 4)
    ident = Group("enrollment", (("student_number", "123456"),), "cube_only", 40, 38)
    cells = CellDiff("enrollment", {"differs": 3, "cube_only": 12})

    items = open_items(
        _run(
            groups=[shown, small, ident],
            gaps=[_gap("Enroll Status"), _gap("Grade", "cut")],
            cells=[cells],
        )
    )

    by_id = {i.id: i for i in items}
    assert "enrollment:grade_level=9" in by_id
    assert "enrollment:student_number=<redacted>" in by_id
    assert "enrollment:cells" in by_id
    assert "filter:Enroll Status" in by_id
    assert "cut:Grade" in by_id
    assert not any("123456" in i.id + i.label + str(i.stub) for i in items)
    # A group under 10 students never shows its value.
    small_item = items[1]
    assert small_item.id == "enrollment:grade_level=<redacted>"
    assert "<10 rows" in small_item.label and "<10 students" in small_item.label
    assert by_id["enrollment:grade_level=9"].stub == {
        "comparison": "enrollment",
        "group": {"column": "grade_level", "values": ["9"]},
    }
    assert by_id["enrollment:cells"].stub == {
        "comparison": "enrollment",
        "cells": True,
    }
    assert by_id["cut:Grade"].stub == {"missing_cut": "Grade"}
    assert by_id["filter:Enroll Status"].stub == {"missing_filter": "Enroll Status"}
    assert open_items(_run(groups=[shown])) == open_items(_run(groups=[shown]))
