# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "google-auth>=2.0",
#   "requests>=2.32",
# ]
# ///

"""Assert deny-sandbox-bigquery still exists on the production project.

Separate from the isolation test because it needs a different identity: this
one reads production IAM, that one acts as the sandbox service account. One
account holding both would be a step toward the cross-project binding the
design exists to prevent.

It is also not redundant with that test. An absent grant and an active deny
policy produce the same 403, so the isolation test cannot tell whether the
boundary rests on the deny policy or merely on nobody having granted access
yet. This catches a later deletion or edit of the policy itself.

Reading a deny policy needs `iam.googleapis.com/denypolicies.list` on
teamster-332318. Nothing on the analytics side holds it today, so this
currently exits UNPROVEN rather than PASS — which is the honest answer, and
why UNPROVEN is a distinct code from FAIL.

Exit codes: 0 pass, 1 fail, 2 unproven.

Design reference:
    docs/superpowers/specs/2026-09-11-cube-sandbox-build-design.md, Piece 1
"""

from __future__ import annotations

import sys

POLICY = "deny-sandbox-bigquery"
ATTACHMENT = "cloudresourcemanager.googleapis.com%2Fprojects%2Fteamster-332318"
ENDPOINT = f"https://iam.googleapis.com/v2/policies/{ATTACHMENT}/denypolicies"

PASS = 0
FAIL = 1
UNPROVEN = 2


def verdict(status_code: int, policy_names: list[str]) -> tuple[int, str]:
    """The run's verdict, split out so it is testable without a live call."""
    if status_code in (401, 403):
        return (
            UNPROVEN,
            (
                "this identity lacks denypolicies.list on teamster-332318, so "
                "the policy's existence was not checked either way"
            ),
        )
    if status_code != 200:
        return UNPROVEN, f"IAM returned {status_code}; the policy was not checked"
    if any(name.rsplit("/", 1)[-1] == POLICY for name in policy_names):
        return PASS, f"{POLICY} exists"
    return (
        FAIL,
        (
            f"{POLICY} not found. Isolation then rests on the absence of a "
            "grant alone, which a later well-meaning grant can undo."
        ),
    )


def main() -> int:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    response = AuthorizedSession(credentials).get(ENDPOINT)
    names = []
    if response.status_code == 200:
        names = [p.get("name", "") for p in response.json().get("policies", [])]

    code, reason = verdict(response.status_code, names)
    print(f"{['PASS', 'FAILED', 'UNPROVEN'][code]} - {reason}")
    return code


if __name__ == "__main__":
    sys.exit(main())
