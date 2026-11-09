"""Drift guard for src/dbt/dbt_overrides' fork of dbt's test materialization.

The fork must equal the installed dbt-adapters built-in with PATCHES applied.
When a dbt upgrade changes the built-in, these tests fail: re-sync the fork from
the new upstream file and re-apply PATCHES.
"""

from pathlib import Path

import dbt.include.global_project

UPSTREAM = (
    Path(dbt.include.global_project.__file__).parent
    / "macros/materializations/tests/test.sql"
)
OURS = (
    Path(__file__).parents[1] / "src/dbt/dbt_overrides/macros/materialization_test.sql"
)
PATCHES = [
    # upstream leaves a stray `%}` after this tag; it renders as discarded text,
    # but sqlfmt (the pre-commit formatter) cannot tokenize the file with it
    (
        "type=store_failures_as) -%} %}",
        "type=store_failures_as) -%}",
    ),
    (
        "{%- materialization test, default -%}",
        "{%- materialization test, adapter='bigquery' -%}",
    ),
    (
        "    {% if old_relation %}\n",
        "    {# create or replace swaps a same-type relation in one step;"
        " dropping first leaves a gap a concurrent run can hit #}\n"
        "    {% if old_relation and old_relation.type != target_relation.type %}\n",
    ),
]


def test_upstream_has_each_patch_site_once():
    upstream = UPSTREAM.read_text()
    for old, _ in PATCHES:
        assert upstream.count(old) == 1, (
            f"dbt changed its built-in test materialization ({UPSTREAM}); "
            f"patch site {old!r} no longer appears exactly once. Re-sync {OURS}."
        )


def test_override_matches_patched_upstream():
    patched = UPSTREAM.read_text()
    for old, new in PATCHES:
        patched = patched.replace(old, new, 1)

    ours = OURS.read_text()
    body = ours[ours.index("{%- materialization") :]

    assert body == patched, (
        f"{OURS} differs from the patched built-in at {UPSTREAM}. "
        "Re-sync it from upstream and re-apply PATCHES."
    )
