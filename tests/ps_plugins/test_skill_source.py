"""The end-user skill's three seeding-time corrections."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "ps-plugins" / "skills" / "gradebook-expectations-upload"
SHEETS = SKILL / "references" / "sheets.md"

IMPORTRANGE_SOURCE_ID = "1ofCxW0pLniywn_XZT69S23vhcDs6y9ElAtJa5fTtiT0"
REPORTS_ID = "1Fx_tc1Bja2IWrIHyidTJrI4a0ZNcds07V29kjtkh3Go"


def test_skill_never_names_the_importrange_source_sheet():
    """Users get the Reports copy; the source is where refreshes are programmed."""
    offenders = [
        p.relative_to(SKILL)
        for p in SKILL.rglob("*.md")
        if IMPORTRANGE_SOURCE_ID in p.read_text()
    ]
    assert offenders == []


def test_sheets_reference_names_the_reports_copy():
    assert REPORTS_ID in SHEETS.read_text()


def test_sheets_reference_explains_the_two_drive_calls():
    text = SHEETS.read_text()
    for token in ("read_file_content", "get_file_metadata", "snippetVerbosity"):
        assert token in text, f"{token} missing; the dropped section was not restored"


def test_skill_uses_the_reports_tab_names():
    """The Reports copy is the user-friendly one; its tabs are named for people."""
    text = SHEETS.read_text()
    for tab in (
        "PS Full Calendar",
        "Plugin Data Raw",
        "Template QW-Date Crosswalk",
        "PS Plugin CSV Template",
    ):
        assert tab in text, f"{tab} is a tab on the Reports copy and is not named"


def test_rollover_no_longer_needs_an_existing_plugin_row():
    """PS Full Calendar carries week numbers, so the anchor problem is gone."""
    rollover = (SKILL / "playbooks" / "rollover.md").read_text()
    assert "PS Full Calendar" in rollover
    assert "🛑" not in (SKILL / "SKILL.md").read_text(), (
        "the open-gap note is answered; a stale warning teaches readers to "
        "distrust the live ones"
    )


def test_both_files_warn_about_the_academic_year_rollover():
    """The tab shows last year's weeks until the warehouse variable flips."""
    for name in ("playbooks/rollover.md", "references/sheets.md"):
        assert "academic_year" in (SKILL / name).read_text(), (
            f"{name} must tell the reader to confirm the academic_year column "
            "before trusting the calendar tab"
        )


def test_skill_never_uses_a_source_sheet_tab_name():
    """Those tabs exist only on the IMPORTRANGE Sources copy, which users never open."""
    offenders = []
    for p in SKILL.rglob("*.md"):
        body = p.read_text()
        for tab in ("ps_plugin_raw", "ps_plugin_data", "ps_all_weeks"):
            if tab in body:
                offenders.append(f"{p.relative_to(SKILL)}: {tab}")
    assert offenders == []
