"""Tests for scripts/cube_sandbox_isolation.py and cube_sandbox_deny_policy.py."""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).parents[2] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module is required for the module's @dataclass
    # to resolve its own forward-referenced types.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _isolation():
    return _load("cube_sandbox_isolation")


def _deny():
    return _load("cube_sandbox_deny_policy")


def test_script_module_loads() -> None:
    assert _isolation() is not None


def test_the_target_account_is_the_sandbox_one() -> None:
    mod = _isolation()
    assert mod.SERVICE_ACCOUNT.endswith(
        "@teamster-cube-sandbox.iam.gserviceaccount.com"
    )
    assert mod.PRODUCTION_TABLE.startswith("teamster-332318.")


# --- classify -------------------------------------------------------------


def test_a_403_is_a_permission_denial_and_a_404_is_not() -> None:
    mod = _isolation()
    assert mod.classify(403, "Access Denied") == mod.PERMISSION
    # A renamed or mistyped production table 404s. Reading that as a denial
    # reports a boundary that was never exercised.
    assert mod.classify(404, "Not found: Table x") == mod.MISSING
    assert mod.classify(500, "backend error") == mod.OTHER


def test_classify_falls_back_to_the_message_when_there_is_no_code() -> None:
    mod = _isolation()
    assert mod.classify(None, "User does not have permission to query") == (
        mod.PERMISSION
    )
    assert mod.classify(None, "Not found: Dataset x") == mod.MISSING
    assert mod.classify(None, "connection reset") == mod.OTHER


# --- decide ---------------------------------------------------------------


def test_both_legs_as_intended_is_a_pass() -> None:
    mod = _isolation()
    code, _ = mod.decide(
        mod.Leg(ran=True, succeeded=True),
        mod.Leg(ran=True, succeeded=False, denial=mod.PERMISSION),
    )
    assert code == mod.PASS


def test_a_failed_positive_leg_is_unproven_not_a_pass() -> None:
    # The whole reason the positive leg runs first. Broken credentials are
    # refused by production exactly like isolated ones, so without this the
    # suite goes green on the day the sandbox breaks.
    mod = _isolation()
    code, reason = mod.decide(
        mod.Leg(ran=True, succeeded=False, denial=mod.PERMISSION, detail="bad key"),
        mod.Leg(ran=True, succeeded=False, denial=mod.PERMISSION),
    )
    assert code == mod.UNPROVEN
    assert "proves nothing" in reason


def test_a_skipped_negative_leg_is_unproven() -> None:
    mod = _isolation()
    code, _ = mod.decide(
        mod.Leg(ran=True, succeeded=True), mod.Leg(ran=False, succeeded=False)
    )
    assert code == mod.UNPROVEN


def test_reading_production_successfully_is_a_hard_failure() -> None:
    mod = _isolation()
    code, reason = mod.decide(
        mod.Leg(ran=True, succeeded=True), mod.Leg(ran=True, succeeded=True)
    )
    assert code == mod.FAIL
    assert "Isolation is broken" in reason


def test_a_missing_production_table_is_unproven_not_a_pass() -> None:
    mod = _isolation()
    code, reason = mod.decide(
        mod.Leg(ran=True, succeeded=True),
        mod.Leg(ran=True, succeeded=False, denial=mod.MISSING),
    )
    assert code == mod.UNPROVEN
    assert "NOT FOUND" in reason


# --- identity guard -------------------------------------------------------


def test_it_refuses_to_run_as_anything_but_the_sandbox_account() -> None:
    # Ambient production credentials can read production, so the negative leg
    # would fail for the wrong reason and report a boundary never tested.
    mod = _isolation()

    class _Creds:
        service_account_email = "someone-else@teamster-332318.iam.gserviceaccount.com"

    with pytest.raises(SystemExit, match="refusing to run as"):
        mod.assert_sandbox_identity(_Creds())


def test_it_accepts_the_sandbox_account() -> None:
    mod = _isolation()

    class _Creds:
        service_account_email = mod.SERVICE_ACCOUNT

    assert mod.assert_sandbox_identity(_Creds()) is None


def test_credentials_with_no_service_account_email_are_refused() -> None:
    # User ADC has no service_account_email at all.
    mod = _isolation()
    with pytest.raises(SystemExit):
        mod.assert_sandbox_identity(object())


# --- deny policy ----------------------------------------------------------


def test_the_deny_policy_is_found_by_its_bare_name() -> None:
    mod = _deny()
    code, _ = mod.verdict(
        200, ["policies/cloudresourcemanager.../denypolicies/deny-sandbox-bigquery"]
    )
    assert code == mod.PASS


def test_a_missing_deny_policy_fails() -> None:
    mod = _deny()
    code, reason = mod.verdict(200, ["policies/other/denypolicies/something-else"])
    assert code == mod.FAIL
    assert "absence of a grant" in reason


def test_no_iam_permission_is_unproven_not_a_pass() -> None:
    # Nothing on the analytics side holds denypolicies.list today, so this is
    # the live answer. Reporting it as a pass would claim a check that did
    # not run.
    mod = _deny()
    for status in (401, 403):
        code, _ = mod.verdict(status, [])
        assert code == mod.UNPROVEN


def test_a_name_that_merely_ends_with_the_policy_string_does_not_match() -> None:
    # `endswith` would match `.../denypolicies/not-deny-sandbox-bigquery`.
    mod = _deny()
    code, _ = mod.verdict(200, ["policies/x/denypolicies/not-deny-sandbox-bigquery"])
    assert code == mod.FAIL


def test_stdin_rejects_an_empty_paste() -> None:
    mod = _isolation()
    # Silently proceeding on an empty paste would surface later as an
    # unrelated credentials error, sending the reader after the wrong thing.
    with pytest.raises(SystemExit, match="nothing arrived on stdin"):
        mod.credentials_from_stdin(io.StringIO(""))


def test_stdin_rejects_malformed_json() -> None:
    mod = _isolation()
    with pytest.raises(SystemExit, match="not valid JSON"):
        mod.credentials_from_stdin(io.StringIO("not json at all"))


def test_stdin_builds_credentials_without_touching_disk(monkeypatch) -> None:
    mod = _isolation()
    seen = {}

    def fake_from_info(info, scopes):
        seen["info"] = info
        seen["scopes"] = scopes
        return "credentials"

    # Patch at the point of use so no key file is needed and no real key
    # material is involved.
    import google.oauth2.service_account as sa

    monkeypatch.setattr(sa.Credentials, "from_service_account_info", fake_from_info)

    result = mod.credentials_from_stdin(io.StringIO('{"client_email": "x@y.invalid"}'))

    assert result == "credentials"
    assert seen["info"] == {"client_email": "x@y.invalid"}
    assert "cloud-platform" in seen["scopes"][0]
