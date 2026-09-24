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
