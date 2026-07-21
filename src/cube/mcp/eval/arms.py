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
            "name": "student_attendance_view",
            "title": "Student Attendance",
            "type": "view",
            "measures": [
                {
                    "name": "student_attendance_view.count_students",
                    "title": "Count Students",
                    "type": "number",
                    "description": "Distinct students served.",
                },
                {
                    "name": "student_attendance_view.count_chronically_absent",
                    "title": "Count Chronically Absent",
                    "type": "number",
                    "description": (
                        "Students flagged chronically absent (under 90% attendance)."
                    ),
                },
                {
                    "name": "student_attendance_view.percent_chronically_absent",
                    "title": "Percent Chronically Absent",
                    "type": "number",
                    "description": "Share of students chronically absent.",
                },
            ],
            "dimensions": [
                {
                    "name": "student_attendance_view.dates_academic_year",
                    "title": "Dates Academic Year",
                    "type": "number",
                    "description": _ACADEMIC_YEAR_DESC,
                },
                {
                    "name": "student_attendance_view.dates_academic_year_label",
                    "title": "Dates Academic Year Label",
                    "type": "string",
                    "description": _ACADEMIC_YEAR_LABEL_DESC,
                },
                {
                    "name": "student_attendance_view.school_abbreviation",
                    "title": "School",
                    "type": "string",
                    "description": "School abbreviation.",
                },
            ],
            "segments": [],
        }
    ]
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
            "input_schema": t.inputSchema,
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
