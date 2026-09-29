"""Arm definitions for the academic-year eval.

Two designs are compared, holding everything constant except the one variable
under test: the academic-year crosswalk paragraph in the ``load`` tool
description.

    A_baseline      shipped tools minus the "resolve it yourself" crosswalk
                    paragraph in load's description — the floor: the rest of
                    the tool descriptions (and the academic-year dimension
                    descriptions) alone.
    B_descriptions  the shipped branch as-is: load's description including the
                    inline crosswalk with worked examples.

The crosswalk moved from the FastMCP ``instructions`` string into the ``load``
tool description (#4473) because ``instructions`` is an unreliable channel —
absent on the claude.ai connector, truncated in Claude Code — while tool
descriptions reach the model on every surface. This eval now measures that
channel: it reads the tool descriptions from the real ``src/cube/mcp/server.py``
and varies only the crosswalk paragraph; ``instructions`` is held constant
(slim) across both arms.

A model-in-the-loop eval (#4084, PR #4125) also compared these against a third
arm that added a deterministic ``resolve_academic_year`` tool. The tool never
beat arm B and on the trap case produced the off-by-one it existed to prevent,
so it was dropped; this harness is retained as the A-vs-B regression guard.

Only the ``load``/``meta``/``sql`` execution is stubbed (see harness.py) so no
warehouse, auth, or PII is involved.
"""

import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"

# Anchors that bracket the shipped "ACADEMIC YEAR — resolve it yourself ..."
# crosswalk paragraph in the real load tool description. Removing the text
# between them yields the crosswalk-free baseline description used by arm A.
_CROSSWALK_ANCHOR = "ACADEMIC YEAR — resolve it yourself"
_AFTER_ANCHOR = "Numeric values come back"

# Fixed /meta payload. Carries the real academic-year dimension descriptions
# (the crosswalk surface) so it is present in every arm; only the crosswalk
# paragraph in the load tool description varies across arms.
_ACADEMIC_YEAR_DESC = (
    "KIPP academic year (July start). The calendar year in which the academic "
    "year begins (e.g., 2025 for the 2025-26 school year). For filtering by "
    'year, prefer academic_year_label (the unambiguous "2025-2026" string '
    "form) over this integer."
)
_ACADEMIC_YEAR_LABEL_DESC = (
    'Full span label for the academic year (e.g. "2025-2026" for the year '
    "beginning July 2025). Use this as the canonical filter surface when "
    "querying by year - it is unambiguous regardless of SY vs. start-year "
    'notation. academic_year 2025 = academic_year_label "2025-2026" = SY26. '
    "The integer academic_year is retained for sort/group/math only."
)

META_STUB: dict[str, Any] = {
    "cubes": [
        {
            "name": "student_attendance_enrollment_daily_view",
            "title": "Student Attendance",
            "type": "view",
            "measures": [
                {
                    "name": "student_attendance_enrollment_daily_view.count_students",
                    "title": "Count Students",
                    "type": "number",
                    "description": (
                        "Distinct students in the queried slice. Pin a date for a "
                        "point-in-time headcount; leave it open for ever-enrolled."
                    ),
                },
            ],
            "dimensions": [
                {
                    "name": "student_attendance_enrollment_daily_view.dates_academic_year",
                    "title": "Dates Academic Year",
                    "type": "number",
                    "description": _ACADEMIC_YEAR_DESC,
                },
                {
                    "name": "student_attendance_enrollment_daily_view.dates_academic_year_label",
                    "title": "Dates Academic Year Label",
                    "type": "string",
                    "description": _ACADEMIC_YEAR_LABEL_DESC,
                },
                {
                    "name": "student_attendance_enrollment_daily_view.school_abbreviation",
                    "title": "School",
                    "type": "string",
                    "description": "School abbreviation.",
                },
            ],
            "segments": [],
        },
        {
            "name": "student_attendance_enrollment_periods_view",
            "title": "Student Attendance Periods",
            "type": "view",
            "measures": [
                {
                    "name": "student_attendance_enrollment_periods_view.count_students",
                    "title": "Count Students",
                    "type": "number",
                    "description": (
                        "Student-school records served at any point in the period. "
                        "Show it beside every rate on this view."
                    ),
                },
                {
                    "name": "student_attendance_enrollment_periods_view.count_chronically_absent",
                    "title": "Count Chronically Absent",
                    "type": "number",
                    "description": (
                        "Students at or below 90.0% cumulative attendance as of "
                        "period end."
                    ),
                },
                {
                    "name": "student_attendance_enrollment_periods_view.pct_chronically_absent",
                    "title": "Percent Chronically Absent",
                    "type": "number",
                    "description": (
                        "Chronic absence rate. Excludes anyone with fewer than 10 "
                        "membership days year-to-date."
                    ),
                },
            ],
            "dimensions": [
                {
                    "name": "student_attendance_enrollment_periods_view.period_type",
                    "title": "Period Type",
                    "type": "string",
                    "description": "year, month, or week.",
                },
                {
                    "name": "student_attendance_enrollment_periods_view.academic_year_label",
                    "title": "Academic Year Label",
                    "type": "string",
                    "description": _ACADEMIC_YEAR_LABEL_DESC,
                },
            ],
            "segments": [],
        },
    ]
}


# --- Placement arms: does it matter WHICH field member guidance lives in? ----
#
# The A/B arms above vary the load docstring. The F arms hold the load docstring
# fixed (crosswalk removed, as in A) and move ONE block of guidance text — the
# crosswalk paragraph lifted verbatim from load — between member fields:
#
#     F0_none     plain definitions, guidance nowhere          floor / headroom
#     F1_desc     guidance appended to the member description   description-only
#     F2_ctx      guidance in the member's meta.ai_context      does the field matter?
#     F3_ctx_ptr  F2 plus one meta-docstring line pointing at   does a pointer matter?
#                 ai_context
#
# The same text rides every arm, so a difference between F1 and F2/F3 is the
# field, not the words. If F0 already scores near zero there is no headroom and
# the run cannot distinguish placements.

_PLAIN_ACADEMIC_YEAR_DESC = "KIPP academic year (July start), as an integer."
_PLAIN_ACADEMIC_YEAR_LABEL_DESC = 'KIPP academic year as a string, e.g. "2025-2026".'

AI_CONTEXT_POINTER = (
    "Members may carry `meta.ai_context`: usage rules written for you. Read and "
    "follow a member's `ai_context` before building a query that uses it."
)

# Placement arms, in report order.
PLACEMENT_ARMS = ["F0_none", "F1_desc", "F2_ctx", "F3_ctx_ptr"]

_YEAR_MEMBERS = {
    "student_attendance_enrollment_daily_view.dates_academic_year": (
        _PLAIN_ACADEMIC_YEAR_DESC
    ),
    "student_attendance_enrollment_daily_view.dates_academic_year_label": (
        _PLAIN_ACADEMIC_YEAR_LABEL_DESC
    ),
    "student_attendance_enrollment_periods_view.academic_year_label": (
        _PLAIN_ACADEMIC_YEAR_LABEL_DESC
    ),
}


def _placement_meta(guidance: str, placement: str | None) -> dict[str, Any]:
    """META_STUB with plain year descriptions and ``guidance`` placed per arm.

    placement: None (nowhere), "description" (appended), or "ai_context"
    (member-level ``meta.ai_context``, the shape Cube's /meta returns).
    """
    import copy

    payload = copy.deepcopy(META_STUB)
    for cube in payload["cubes"]:
        for dim in cube["dimensions"]:
            plain = _YEAR_MEMBERS.get(dim["name"])
            if plain is None:
                continue
            dim["description"] = plain
            if placement == "description":
                dim["description"] = f"{plain} {guidance}"
            elif placement == "ai_context":
                dim["meta"] = {"ai_context": guidance}
    return payload


def build_placement_arms(server: ModuleType) -> dict[str, dict[str, Any]]:
    """Return {arm_name: {"instructions", "tools", "meta"}} for the F arms."""
    base = build_arms(server)["A_baseline"]
    load_desc = next(t for t in base["tools"] if t["name"] == "load")
    full_load = _anthropic_tools(server)["load"]["description"]
    start = full_load.find(_CROSSWALK_ANCHOR)
    end = full_load.find(_AFTER_ANCHOR)
    guidance = " ".join(full_load[start:end].split())
    if not guidance or len(guidance) > 2000:
        raise RuntimeError(
            f"crosswalk guidance is {len(guidance)} chars; ai_context caps at 2,000"
        )

    def _tools(meta_suffix: str = "") -> list[dict[str, Any]]:
        meta_tool = next(t for t in base["tools"] if t["name"] == "meta")
        sql_tool = next(t for t in base["tools"] if t["name"] == "sql")
        return [
            {**meta_tool, "description": meta_tool["description"] + meta_suffix},
            load_desc,
            sql_tool,
        ]

    pointer = "\n\n    " + AI_CONTEXT_POINTER
    return {
        "F0_none": {
            "instructions": base["instructions"],
            "tools": _tools(),
            "meta": _placement_meta(guidance, None),
        },
        "F1_desc": {
            "instructions": base["instructions"],
            "tools": _tools(),
            "meta": _placement_meta(guidance, "description"),
        },
        "F2_ctx": {
            "instructions": base["instructions"],
            "tools": _tools(),
            "meta": _placement_meta(guidance, "ai_context"),
        },
        "F3_ctx_ptr": {
            "instructions": base["instructions"],
            "tools": _tools(pointer),
            "meta": _placement_meta(guidance, "ai_context"),
        },
    }


def load_server() -> ModuleType:
    """Import src/cube/mcp/server.py with placeholder env (mirrors the test).

    server.py reads CUBE_REST_URL / CUBE_API_SECRET at import time; neither is
    used here because every Cube call is stubbed in the harness.
    """
    if "cube_mcp_server" in sys.modules:
        return sys.modules["cube_mcp_server"]
    os.environ.setdefault("CUBE_REST_URL", "https://example.invalid/cubejs-api/v1")
    os.environ.setdefault("CUBE_API_SECRET", "placeholder-not-used")
    spec = importlib.util.spec_from_file_location("cube_mcp_server", _SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["cube_mcp_server"] = module
    spec.loader.exec_module(module)
    return module


def _anthropic_tools(server: ModuleType) -> dict[str, dict[str, Any]]:
    """Read the real registered tools and convert to Anthropic tool format."""
    raw = asyncio.run(server.mcp.list_tools())
    return {
        t.name: {
            "name": t.name,
            "description": t.description or "",
            # mcp SDK 2.0 renamed Tool.inputSchema to input_schema.
            "input_schema": t.input_schema,
        }
        for t in raw
    }


def build_arms(server: ModuleType) -> dict[str, dict[str, Any]]:
    """Return {arm_name: {"instructions": str, "tools": list[tool-dict]}}.

    ``instructions`` is held constant (the shipped slim string) across arms; the
    A-vs-B variable is the academic-year crosswalk paragraph in the ``load``
    tool description, which arm A has removed.
    """
    tools = _anthropic_tools(server)
    missing = {"meta", "load", "sql"} - set(tools)
    if missing:
        raise RuntimeError(f"server.py is missing expected tools: {sorted(missing)}")

    instructions = server.mcp.instructions or ""
    load_desc = tools["load"]["description"]
    start = load_desc.find(_CROSSWALK_ANCHOR)
    end = load_desc.find(_AFTER_ANCHOR)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(
            "Could not locate the academic-year crosswalk paragraph in the "
            "load tool description; anchors may have changed — update "
            "_CROSSWALK_ANCHOR/_AFTER_ANCHOR."
        )
    load_no_crosswalk = load_desc[:start] + load_desc[end:]

    def _tools_with_load(desc: str) -> list[dict[str, Any]]:
        return [
            tools["meta"],
            {**tools["load"], "description": desc},
            tools["sql"],
        ]

    return {
        "A_baseline": {
            "instructions": instructions,
            "tools": _tools_with_load(load_no_crosswalk),
        },
        "B_descriptions": {
            "instructions": instructions,
            "tools": _tools_with_load(load_desc),
        },
    }
