"""Bucket 1 and Bucket 4. Runs last."""

from __future__ import annotations

from teamster.goal_setting.records import StudentRecord


def _fmt(score: float | None) -> str:
    return "untested" if score is None else f"{score:g}"


def finalize(records: list[StudentRecord]) -> list[StudentRecord]:
    out = []
    for r in records:
        if r.is_proficient:
            out.append(
                r.with_(
                    bucket="Bucket 1",
                    reason=(
                        f"proficient, projected {_fmt(r.projected_score)} "
                        f"at level {r.projected_level}"
                    ),
                )
            )
        elif r.bucket in ("Bucket 2", "Bucket 3"):
            out.append(r)
        elif not r.is_tested:
            out.append(
                r.with_(
                    bucket="Bucket 4", bucket4_outcome="untested", reason="untested"
                )
            )
        else:
            if r.reason:
                reason = r.reason
            elif r.is_approaching:
                reason = (
                    f"projected level {r.projected_level}, approaching, not selected"
                )
            else:
                reason = f"projected level {r.projected_level}, below approaching"
            out.append(
                r.with_(bucket="Bucket 4", bucket4_outcome="below", reason=reason)
            )
    return out
