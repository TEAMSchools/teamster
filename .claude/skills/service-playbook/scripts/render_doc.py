"""Render a service playbook as HTML for Drive to convert into a Google Doc.

Inputs are three JSON files: the playbook's prose (``content.json``), the
``capacity.py`` spec (``playbook.json``) and ``capacity.py``'s output
(``capacity.json``). Their shapes are in ``references/playbook-doc.md``. The
twelve tables follow that file's section list. Hours are always printed with
``[proposed]``; the owner deletes the marker in the doc when they accept a
figure. Text is escaped, and a link is kept only when it starts with https://.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

MONTHS = [
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
]
P = "[proposed] "


def _cell(value: object, bold: bool = False) -> str:
    text = html.escape(str(value))
    return f"<td><b>{text}</b></td>" if bold else f"<td>{text}</td>"


def _link(url: str, text: str) -> str:
    if isinstance(url, str) and url.startswith("https://"):
        return f'<td><a href="{html.escape(url)}">{html.escape(text)}</a></td>'
    return "<td></td>"


def _table(title: str, header: Sequence[str] | None, rows: list[str]) -> str:
    n = len(header) if header else 2
    out = [
        '<table border="1" cellpadding="6" style="border-collapse:collapse;width:100%">',
        f'<tr><td colspan="{n}" style="background:#d9e2f3"><b>{html.escape(title)}</b></td></tr>',
    ]
    if header:
        out.append("<tr>" + "".join(_cell(h, bold=True) for h in header) + "</tr>")
    out.extend("<tr>" + r + "</tr>" for r in rows)
    out.append("</table><p></p>")
    return "\n".join(out)


def _pairs(rows: list[tuple[str, str]]) -> list[str]:
    return [_cell(k, bold=True) + _cell(v) for k, v in rows]


def _week(d: str) -> str:
    day = date.fromisoformat(d)
    monday = day - timedelta(days=day.weekday())
    return "week of " + monday.strftime("%b %-d")


def _anchor(step: dict) -> str:
    off = step["offset_weeks"]
    if off == 0:
        return f"{step['anchor']} week"
    side = "before" if off < 0 else "after"
    unit = "week" if abs(off) == 1 else "weeks"
    return f"{abs(off)} {unit} {side} {step['anchor']}"


def render(content: dict, playbook: dict, capacity: dict) -> str:
    hours = capacity["hours_by_month"]
    busiest = sorted(range(12), key=lambda i: -hours[i])[:3]
    rounds = content["rounds"]
    keyed = {r["key"]: r["name"] for r in rounds}
    body = [
        f"<h1>{html.escape(content['workstream'])} - Service Playbook</h1>",
        "<p><i>Built by the service-playbook skill. Lines starting with [proposed] are "
        "drafts: change or confirm them, then delete the marker.</i></p>",
    ]

    summary = _pairs(
        [
            ("Service name", content["workstream"]),
            ("Owner", content["owner"]),
            ("Backup", content["backup"]),
            ("Partner team", content["partner_team"]),
        ]
    )
    summary.append(
        _cell("Asana project", bold=True) + _link(content.get("asana_url", ""), "Asana")
    )
    summary += _pairs(
        [
            ("Date source", content["date_source"]),
            ("Hours per year", P + f"{capacity['hours_per_year']:g}"),
            (
                "Busiest months",
                P + ", ".join(f"{MONTHS[i]} ({hours[i]:g} h)" for i in busiest),
            ),
        ]
    )
    body.append(_table("SERVICE SUMMARY", None, summary))
    body.append(
        _table(
            "WHAT AND WHY",
            None,
            _pairs(
                [
                    ("What the service delivers", content["what"]),
                    ("Why it matters", content["why"]),
                ]
            ),
        )
    )
    body.append(
        _table(
            "SCOPE",
            None,
            _pairs(
                [
                    ("Data team supports", content["supports"]),
                    ("Partner team owns", content["partner_owns"]),
                ]
            ),
        )
    )
    body.append(
        _table(
            "STAKEHOLDER MAP",
            [
                "Stakeholder",
                "Power (H/M/L)",
                "Interest (H/M/L)",
                "Current Position",
                "Key Concerns",
                "Engagement Level",
            ],
            ["".join(_cell(c) for c in row) for row in content["stakeholders"]],
        )
    )
    roles = content["roles"]
    body.append(
        _table(
            "ROLES & OWNERSHIP",
            None,
            _pairs(
                [
                    (
                        "M — Manager (holds Owner accountable, approves decisions)",
                        roles["M"],
                    ),
                    ("O — Owner (runs the service; full accountability)", roles["O"]),
                    ("C — Consulted (expertise needed; must be consulted)", roles["C"]),
                    ("H — Helper (completes specific assigned tasks)", roles["H"]),
                    ("A — Approver (signs off on key decisions)", roles["A"]),
                ]
            ),
        )
    )
    body.append(
        _table(
            "ROUND CALENDAR",
            ["Round", "Includes", "Open week", "Close week"],
            [
                _cell(r["name"])
                + _cell(r["includes"])
                + _cell(P + _week(r["open_week"]))
                + _cell(P + _week(r["close_week"]))
                for r in rounds
            ],
        )
    )
    body.append(
        _table(
            "ROUND CHECKLIST",
            ["Step", "When", "Duration weeks", "Hours per week", "Role", "Rounds"],
            [
                _cell(s["name"])
                + _cell(_anchor(s))
                + _cell(s["duration_weeks"])
                + _cell(P + f"{s['hours_per_week']:g}")
                + _cell(s["role"])
                + _cell(
                    "all"
                    if s.get("rounds") is None
                    else ", ".join(keyed.get(k, k) for k in s["rounds"])
                )
                for s in playbook.get("steps", [])
            ],
        )
    )
    body.append(
        _table(
            "STANDING WORK",
            ["Work", "Hours per week", "Weeks"],
            [
                _cell(s["name"])
                + _cell(P + f"{s['hours_per_week']:g}")
                + _cell(
                    "school weeks, skipping network breaks"
                    if s["weeks"] == "school_year"
                    else "every week, July to June"
                )
                for s in playbook.get("standing", [])
            ],
        )
    )
    body.append(
        _table(
            "CAPACITY SUMMARY (computed by capacity.py; do not edit by hand)",
            ["Month", "Hours"],
            [_cell(m) + _cell(f"{h:g}") for m, h in zip(MONTHS, hours, strict=True)]
            + [_cell("Total", bold=True) + _cell(f"{capacity['hours_per_year']:g}")],
        )
    )
    body.append(
        _table(
            "SYSTEMS",
            ["System", "What it does in this service", "Link"],
            [
                _cell(name) + _cell(what) + _link(url, "Link")
                for name, what, url in content["systems"]
            ],
        )
    )
    body.append(
        _table(
            "RAPID DECISION LOG",
            [
                "Decision",
                "R — Recommend",
                "A — Agree",
                "P — Perform",
                "I — Input",
                "D — Decide",
            ],
            ["".join(_cell(c) for c in row) for row in content["rapid"]],
        )
    )
    body.append(
        _table(
            "KNOWN FAILURE MODES",
            ["Failure", "What it looks like", "Fix"],
            ["".join(_cell(c) for c in row) for row in content["failure_modes"]],
        )
    )
    return (
        '<html><body style="font-family:Calibri, Verdana, sans-serif">'
        + "\n".join(body)
        + "</body></html>"
    )


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render a service playbook as HTML.")
    p.add_argument("--content", required=True, type=Path)
    p.add_argument("--playbook", required=True, type=Path)
    p.add_argument("--capacity", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        page = render(
            *(
                json.loads(f.read_text())
                for f in (args.content, args.playbook, args.capacity)
            )
        )
    except (KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.out.write_text(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
