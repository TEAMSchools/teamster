from __future__ import annotations

import json
from pathlib import Path

from teamster.cube_sandbox import model, personas

CUBE_ROOT = Path(__file__).parents[2] / "src" / "cube"
PERSONAS = CUBE_ROOT / "sandbox" / "personas.yml"
SNAPSHOT = CUBE_ROOT / "sandbox" / "schema_snapshot.json"
ACCESS_TABLE = "dim_staff_cube_access"


def _snapshot_scope_columns() -> set[str]:
    snap = json.loads(SNAPSHOT.read_text())
    return {c for c in snap["tables"][ACCESS_TABLE] if c.endswith("_scope")}


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


def test_every_persona_declares_every_scope_column_in_the_snapshot() -> None:
    """The scope set comes from the DATA, not from a grep of access.js.

    personas.yml shipped declaring five of dim_staff_cube_access's seven
    `*_scope` columns because the set was derived by grepping access.js for
    `*_scope`, and the two remit columns (staff_location_scope,
    staff_department_scope) arrive there as bare parameters — `locationScope`
    and `deptScope` — so neither name appears in the file. The committed
    snapshot is the only place all seven are written down as columns, so this
    asserts against it. Equality, not a subset either way: a persona missing
    a column resolves differently from what it claims, and a persona
    declaring a column the table does not have would be written to a row that
    drops it.
    """
    columns = _snapshot_scope_columns()
    assert len(columns) >= 2, f"{SNAPSHOT} lists no scope columns for {ACCESS_TABLE}"
    for p in personas.load(PERSONAS):
        assert set(p.scopes) == columns, (
            f"{p.email} misses {sorted(columns - set(p.scopes))} and declares "
            f"{sorted(set(p.scopes) - columns)} that the snapshot does not have"
        )


def test_scope_values_cover_every_snapshot_scope_column() -> None:
    # The same drift one layer down: the manifest's scope cells come from
    # model.scope_values, so a column it cannot see gets no coverage cell and
    # no persona is ever required to exercise it.
    values = model.scope_values(CUBE_ROOT / "access.js")
    assert _snapshot_scope_columns() <= set(values), sorted(
        _snapshot_scope_columns() - set(values)
    )


# Mirrors access.js: `computeAllowedAbbreviations` returns [] for any
# locationScope that is not one of its `case` labels, `computeAllowedDepartment
# Groups` likewise for deptScope, and `buildGroups` computes
# `hasRemit = allowedAbbreviations.length > 0 && allowedDepartmentGroups.length
# > 0`. Update this alongside access.js. Exercising the real JS from pytest
# would need a node subprocess for a three-line contract, so the contract is
# mirrored instead — but the legal VALUES are read from access.js via
# model.scope_values rather than copied, so only the shape of the rule lives
# here. The mirror assumes the identity columns the helpers also read
# (region_key, location_abbreviation, department_group) are non-null on a
# persona row; tests/cube_sandbox/test_generate.py asserts that against the
# generated rows.
def _has_remit(person: personas.Persona, scopes: dict[str, set[str]]) -> bool:
    return all(
        person.scopes.get(column) in scopes.get(column, set())
        for column in ("staff_location_scope", "staff_department_scope")
    )


# What each persona's stated `purpose` promises about its remit. Keyed by
# email and complete, so adding a persona forces the decision rather than
# defaulting it.
_EXPECTED_REMIT = {
    "diana.taurasi@ktaf-sandbox.invalid": True,  # "full staff PII remit"
    "ororo.munroe@ktaf-sandbox.invalid": True,  # school-scoped manager
    "zydrunas.ilgauskas@ktaf-sandbox.invalid": True,  # teaching-staff PII
    "aja.ogwumike@ktaf-sandbox.invalid": False,  # "default-deny on every axis"
    "karl-anthony.maximoff@ktaf-sandbox.invalid": True,  # "both a remit and a chain"
    "shaquille.oneal@ktaf-sandbox.invalid": True,  # denied by chain, not remit
}


def test_each_persona_resolves_the_remit_its_purpose_claims() -> None:
    scopes = model.scope_values(CUBE_ROOT / "access.js")
    people = personas.load(PERSONAS)
    assert {p.email for p in people} == set(_EXPECTED_REMIT), (
        "a persona was added or renamed without deciding its remit"
    )
    for p in people:
        assert _has_remit(p, scopes) is _EXPECTED_REMIT[p.email], (
            f"{p.email} resolves hasRemit {_has_remit(p, scopes)}: {p.purpose}"
        )


def test_a_remit_gated_pii_scope_never_resolves_an_empty_remit() -> None:
    # The rule behind the table above, so a NEW persona is caught by the
    # contract and not only by the roster. buildGroups withholds the
    # staff-pii group entirely when hasRemit is false, so an all_in_scope or
    # teaching_staff persona with an empty remit default-denies — the exact
    # opposite of what declaring that scope says.
    scopes = model.scope_values(CUBE_ROOT / "access.js")
    for p in personas.load(PERSONAS):
        if p.scopes.get("staff_pii_scope") in {"all_in_scope", "teaching_staff"}:
            assert _has_remit(p, scopes), f"{p.email} would silently default-deny"


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
