"""Arm definitions for the academic-year resolver eval.

Three designs are compared, holding everything constant except the two
variables under test: the FastMCP ``instructions`` string and whether the
``resolve_academic_year`` tool is offered.

    A_baseline      current instructions minus the "REQUIRED: call
                    resolve_academic_year" paragraph; no resolver tool.
    B_instructions  same, plus a strengthened inline crosswalk with worked
                    examples telling the model to convert the year itself.
    C_tool          the branch as-is: REQUIRED paragraph + resolver tool.

Tool schemas and the instructions string are read from the real
``src/cube/mcp/server.py`` so the eval measures the shipped surface, not a
hand-written approximation. Only the ``load``/``meta``/``sql`` execution is
stubbed (see harness.py) so no warehouse, auth, or PII is involved.
"""

import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"

# Anchors that bracket the "REQUIRED: ... resolve_academic_year ..." paragraph
# in the real instructions string. Removing the text between them yields the
# resolver-free instructions used by arms A and B.
_REQUIRED_ANCHOR = "REQUIRED: Before building"
_AFTER_ANCHOR = "Numeric values come back"

# Arm B's replacement: tell the model to do the conversion itself, with worked
# examples covering the same crosswalk the resolver encodes. This is the
# "can good prompting alone fix it?" arm.
_INLINE_CROSSWALK = (
    "ACADEMIC YEAR — resolve it yourself before building any query that names "
    "a year:\n"
    "- academic_year is the START year; 'SY' notation uses the END year.\n"
    "- 'SY26' -> academic_year 2025, label '2025-2026' (SY end year minus 1).\n"
    "- '2025-26', '2025-2026', 'AY2025' -> academic_year 2025, label "
    "'2025-2026'.\n"
    "- bare '2026' -> treat as the START year (academic_year 2026, label "
    "'2026-2027'); if the user's wording implies SY / end-year, note the other "
    "reading.\n"
    "State your interpretation inline (e.g. 'Interpreting as the 2025-2026 "
    "school year') before showing results, then proceed.\n\n"
)

# Fixed /meta payload. Carries the real academic-year dimension descriptions
# (the crosswalk surface) so it is present in every arm; only instructions and
# the resolver tool vary across arms.
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
            "name": "student_attendance_summary",
            "title": "Student Attendance Summary",
            "type": "view",
            "measures": [
                {
                    "name": "student_attendance_summary.count_students",
                    "title": "Count Students",
                    "type": "number",
                    "description": "Distinct students served.",
                },
                {
                    "name": "student_attendance_summary.count_chronically_absent",
                    "title": "Count Chronically Absent",
                    "type": "number",
                    "description": (
                        "Students flagged chronically absent (under 90% attendance)."
                    ),
                },
                {
                    "name": "student_attendance_summary.percent_chronically_absent",
                    "title": "Percent Chronically Absent",
                    "type": "number",
                    "description": "Share of students chronically absent.",
                },
            ],
            "dimensions": [
                {
                    "name": "student_attendance_summary.dates_academic_year",
                    "title": "Dates Academic Year",
                    "type": "number",
                    "description": _ACADEMIC_YEAR_DESC,
                },
                {
                    "name": "student_attendance_summary.dates_academic_year_label",
                    "title": "Dates Academic Year Label",
                    "type": "string",
                    "description": _ACADEMIC_YEAR_LABEL_DESC,
                },
                {
                    "name": "student_attendance_summary.school_abbreviation",
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
    """Return {arm_name: {"instructions": str, "tools": list[tool-dict]}}."""
    tools = _anthropic_tools(server)
    missing = {"meta", "load", "sql", "resolve_academic_year"} - set(tools)
    if missing:
        raise RuntimeError(f"server.py is missing expected tools: {sorted(missing)}")

    base = server.mcp.instructions
    start = base.find(_REQUIRED_ANCHOR)
    end = base.find(_AFTER_ANCHOR)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(
            "Could not locate the REQUIRED resolver paragraph in instructions; "
            "anchors may have changed — update _REQUIRED_ANCHOR/_AFTER_ANCHOR."
        )
    no_resolver = base[:start] + base[end:]
    with_crosswalk = base[:start] + _INLINE_CROSSWALK + base[end:]

    query_tools = [tools["meta"], tools["load"], tools["sql"]]
    return {
        "A_baseline": {
            "instructions": no_resolver,
            "tools": query_tools,
        },
        "B_instructions": {
            "instructions": with_crosswalk,
            "tools": query_tools,
        },
        "C_tool": {
            "instructions": base,
            "tools": [*query_tools, tools["resolve_academic_year"]],
        },
    }
