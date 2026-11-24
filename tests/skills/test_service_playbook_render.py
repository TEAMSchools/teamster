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


render = _load("render_doc")

TITLES = [
    "SERVICE SUMMARY",
    "WHAT AND WHY",
    "SCOPE",
    "STAKEHOLDER MAP",
    "ROLES & OWNERSHIP",
    "ROUND CALENDAR",
    "ROUND CHECKLIST",
    "STANDING WORK",
    "CAPACITY SUMMARY",
    "SYSTEMS",
    "RAPID DECISION LOG",
    "KNOWN FAILURE MODES",
]


def _content():
    return {
        "slug": "x",
        "workstream": "Example <b>",
        "owner": "Owner A",
        "backup": "[proposed] None",
        "partner_team": "Talent",
        "asana_url": "https://app.asana.com/x",
        "date_source": "PM calendar",
        "rounds": [
            {
                "key": "r1",
                "name": "Round 1",
                "includes": "A",
                "open_week": "2026-10-19",
                "close_week": "2026-11-02",
            }
        ],
        "what": "w",
        "why": "y",
        "supports": "s",
        "partner_owns": "p",
        "stakeholders": [["Talent", "H", "H", "Supportive", "c", "Decide"]],
        "roles": {"M": "m", "O": "Owner A", "C": "c", "H": "h", "A": "a"},
        "systems": [
            ["Dash", "shows", "https://example.org/d"],
            ["Bad", "x", "javascript:alert(1)"],
        ],
        "rapid": [["d", "R", "A", "P", "I", "D"]],
        "failure_modes": [["f", "looks", "fix"]],
        "questions": [],
    }


def _playbook():
    return {
        "windows": [
            {"round_key": "r1", "open_week": "2026-10-19", "close_week": "2026-11-02"}
        ],
        "steps": [
            {
                "name": "Turn on",
                "anchor": "open",
                "offset_weeks": 0,
                "duration_weeks": 1,
                "hours_per_week": 1,
                "role": "owner",
                "rounds": None,
            }
        ],
        "standing": [{"name": "Tickets", "hours_per_week": 1, "weeks": "school_year"}],
    }


def _capacity():
    return {
        "steps": [],
        "hours_by_month": [0, 1, 2, 3, 9, 1, 1, 1, 1, 1, 1, 0],
        "hours_per_year": 21,
    }


def test_render_has_twelve_sections_in_order():
    html = render.render(_content(), _playbook(), _capacity())
    positions = [html.index(t.replace("&", "&amp;")) for t in TITLES]
    assert positions == sorted(positions)
    assert html.count("<table") == 12


def test_render_escapes_text_and_drops_non_https_links():
    html = render.render(_content(), _playbook(), _capacity())
    assert "Example &lt;b&gt;" in html
    assert 'href="https://example.org/d"' in html
    assert "javascript:" not in html


def test_render_adds_open_questions_only_when_there_are_some():
    content = _content()
    content["questions"] = ["Is Q1 <done>?"]
    html = render.render(content, _playbook(), _capacity())
    assert html.count("<table") == 13
    assert html.index("OPEN QUESTIONS") > html.index("KNOWN FAILURE MODES")
    assert "Is Q1 &lt;done&gt;?" in html


def test_render_marks_hours_proposed_and_busiest_months():
    html = render.render(_content(), _playbook(), _capacity())
    assert (
        "[proposed] 1" in html
    )  # step hours stay proposed until the owner clears them
    assert "November (9 h)" in html
