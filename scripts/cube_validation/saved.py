"""Name each comparison's saved unmatched rows in the validator's scratch dataset.

`run` saves every comparison's unmatched rows to one table, so `triage` reads
them instead of rebuilding both sides. The rows are student-level: they stay in
BigQuery, in a dataset only the Data Team can read, and expire on their own.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from .report import run_stamp
from .timetravel import PROJECT

if TYPE_CHECKING:
    from .moment import Build

# The owner creates it once, with a default table expiration and Data Team-only
# access; the validator creates and replaces tables inside it and nowhere else.
SCRATCH_DATASET = "cube_validation_scratch"
# Each saved table also expires on its own, whatever the dataset's default.
SAVED_DAYS = 14
# The reconcile buckets a saved table holds: every bucket but `match`.
SAVED_BUCKETS = ("value_differs", "dims_differ", "dashboard_only", "cube_only")

# BigQuery takes at most 63 characters in a label value.
_LABEL_MAX = 63


def table_id(view: str, build: Build, comparison_id: str) -> str:
    """The dotted id of a comparison's saved table for one run.

    Stable for a view, moment and comparison, so saving again replaces it. The
    hash of the comparison id keeps 2 ids that differ only in punctuation
    apart.
    """
    name = re.sub(
        r"[^a-z0-9_]", "_", f"{view}__{run_stamp(build)}__{comparison_id}".lower()
    )
    digest = hashlib.sha256(comparison_id.encode()).hexdigest()[:8]
    return f"{PROJECT}.{SCRATCH_DATASET}.{name}_{digest}"


def table_sql(table_id: str) -> str:
    """The table as SQL names it: each part in its own backticks."""
    return ".".join(f"`{part}`" for part in table_id.split("."))


def _label(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "_", value.lower())[:_LABEL_MAX]


def labels(
    view: str, build: Build, comparison_id: str, fingerprint: str
) -> dict[str, str]:
    """The labels that say which run and SQL a saved table belongs to.

    Args:
        view: The Cube view.
        build: The run's moment.
        comparison_id: The comparison whose rows the table holds.
        fingerprint: The comparison's checkpoint fingerprint (its config entry
            and both sides' SQL); only its first 32 characters are kept.
    """
    return {
        "view": _label(view),
        "moment": _label(run_stamp(build)),
        "comparison": _label(comparison_id),
        "fingerprint": _label(fingerprint[:32]),
    }
