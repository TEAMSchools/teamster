from __future__ import annotations

from pathlib import Path

from teamster.cube_sandbox import personas

PERSONAS = Path(__file__).parents[2] / "src" / "cube" / "sandbox" / "personas.yml"


def test_every_persona_uses_an_invalid_domain() -> None:
    for p in personas.load(PERSONAS):
        # RFC 2606 reserves .invalid, so no fabricated address can collide
        # with a real account or receive mail.
        assert p.email.endswith(".invalid"), p.email


def test_emails_are_ascii() -> None:
    for p in personas.load(PERSONAS):
        # google_email is the key resolveAccess matches exactly. A non-ASCII
        # address is a realistic-looking identity that resolves to nobody.
        assert p.email.isascii(), p.email


def test_reporting_chain_scope_covers_both_empty_and_nonempty_chains() -> None:
    # access.js only emits staff-pii-reporting_chain when reporteeStaffKeys is
    # non-empty; an empty chain takes the no-group default-deny path instead
    # of the "Values required for filter" hard error Cube throws on an
    # equals-[] row_level filter. That guard is unreachable in production by
    # design, so the sandbox is the only place either side can be exercised —
    # pin both so a later edit can't quietly drop one.
    chain_lengths = {
        len(p.reportees)
        for p in personas.load(PERSONAS)
        if p.scopes.get("staff_pii_scope") == "reporting_chain"
    }
    assert 0 in chain_lengths, "no reporting_chain persona has an EMPTY chain"
    assert any(n > 0 for n in chain_lengths), (
        "no reporting_chain persona has a NON-EMPTY chain"
    )
