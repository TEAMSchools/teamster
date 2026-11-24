from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SKILL_SCRIPTS = (
    Path(__file__).resolve().parents[2] / ".claude/skills/service-playbook/scripts"
)


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SKILL_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tabs = _load("doc_tabs")

PAGE = (
    '<table><tr><td colspan="2"><b>SYSTEMS</b></td></tr>'
    "<tr><td><b>System</b></td><td><b>Link</b></td></tr>"
    '<tr><td>Dash &amp; HQ</td><td><a href="https://x.org">Link</a></td></tr></table>'
    '<table><tr><td colspan="2"><b>SUMMARY</b></td></tr>'
    "<tr><td><b>Owner</b></td><td>Owner A</td></tr></table>"
)


def _doc(tab_id):
    def table(start, rows):
        # Each empty cell holds one paragraph; positions only need to be distinct and rising.
        return {
            "startIndex": start,
            "table": {
                "tableRows": [
                    {
                        "tableCells": [
                            {"content": [{"startIndex": start + 1 + r * 4 + c * 2}]}
                            for c in range(2)
                        ]
                    }
                    for r in range(rows)
                ]
            },
        }

    return {
        "tabs": [
            {
                "tabProperties": {"tabId": "t.0"},
                "documentTab": {"body": {"content": []}},
            },
            {
                "tabProperties": {"tabId": tab_id},
                "documentTab": {
                    "body": {"content": [{"paragraph": {}}, table(10, 3), table(30, 2)]}
                },
            },
        ]
    }


def test_parse_tables_keeps_text_bold_links_and_colspan():
    t = tabs.parse_tables(PAGE)
    assert len(t) == 2
    assert t[0][0] == [("SYSTEMS", True), ("", False)]
    assert t[0][2] == [("Dash & HQ", False), ("https://x.org", False)]
    assert t[1][1] == [("Owner", True), ("Owner A", False)]


def test_skeleton_appends_one_table_per_section_to_the_tab():
    reqs = tabs.skeleton(tabs.parse_tables(PAGE), "t.9")
    assert [r["insertTable"]["rows"] for r in reqs] == [3, 2]
    assert all(
        r["insertTable"]["endOfSegmentLocation"] == {"tabId": "t.9"} for r in reqs
    )


def test_fill_shades_title_and_header_rows_then_inserts_highest_index_first():
    reqs = tabs.fill(_doc("t.9"), "t.9", tabs.parse_tables(PAGE))
    shaded = [
        r["updateTableCellStyle"]["tableRange"]["tableCellLocation"]
        for r in reqs
        if "updateTableCellStyle" in r
    ]
    # SYSTEMS: title row and the all-bold header row; SUMMARY: title only (label/value row is not a header)
    assert [(s["tableStartLocation"]["index"], s["rowIndex"]) for s in shaded] == [
        (10, 0),
        (10, 1),
        (30, 0),
    ]
    inserts = [r["insertText"] for r in reqs if "insertText" in r]
    assert [i["location"]["index"] for i in inserts] == sorted(
        (i["location"]["index"] for i in inserts), reverse=True
    )
    assert {i["location"]["tabId"] for i in inserts} == {"t.9"}
    assert "Dash & HQ" in [i["text"] for i in inserts]
    first_insert = next(n for n, r in enumerate(reqs) if "insertText" in r)
    assert all("insertText" in r for r in reqs[first_insert:])


def test_fill_refuses_a_tab_with_the_wrong_table_count():
    t = tabs.parse_tables(PAGE)
    try:
        tabs.fill(_doc("t.9"), "t.9", t[:1])
    except ValueError as exc:
        assert "expected 1" in str(exc)
    else:
        raise AssertionError("fill accepted a table count mismatch")
