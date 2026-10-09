"""Check dbt models against the architecture rules in .claude/rules/dbt-architecture.md.

Usage: uv run scripts/check_dbt_standard.py --project-dir src/dbt/<project>
    [--diff <git diff -U0 file>] [--write-baseline] [--check-issues]

Edge rules (A1, A8) run over the whole manifest against a per-project baseline
of known violations; a baseline line must name an open tracking issue
(--check-issues looks each one up) and is removed once fixed. Changed-line rules
(A3, A4, A7, A9) need --diff. A model opts out of a rule with
config.meta.standard_exempt: {<rule>: <reason>}.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

# Allowed edges table, child layer -> parent layers. Narrower cases (same-folder
# rules, district wrappers) are handled in _allowed.
ALLOWED: dict[str, set[str]] = {
    "stg": {"source"},
    "source_int": {"stg", "source_int", "snapshot", "source"},
    "domain_int": {"stg", "source_int", "domain_int", "snapshot"},
    "mart": {"domain_int", "mart"},
    "rpt": {"mart", "domain_int"},
    "exposure": {"rpt", "mart"},
    "cube": {"mart"},
}

_PREFIXES = [
    ("stg_", "stg"),
    ("int_", "int"),
    ("base_", "int"),
    ("dim_", "mart"),
    ("fct_", "mart"),
    ("bridge_", "mart"),
    ("rpt_", "rpt"),
    ("snapshot_", "snapshot"),
]

# kipptaf folders whose int_ models are domain intermediates (A11). Kept here,
# not as a dbt_project.yml +meta tag: a tag marks every model in the folder
# state:modified and fans out dbt Cloud CI.
DOMAIN_FOLDERS = {
    "assessments",
    "extracts",
    "finance",
    "gpa",
    "people",
    "performance_management",
    "reporting",
    "students",
    "surveys",
    "topline",
}

# Config inputs a source intermediate may read beside its own folder.
_CONFIG_FOLDERS = {"google"}


@dataclass(frozen=True)
class Violation:
    model: str
    rule: str
    detail: str
    severity: Literal["error", "warning"]
    message: str


def _prefix_layer(name: str) -> str:
    for prefix, layer in _PREFIXES:
        if name.startswith(prefix):
            return layer
    return "other"


def _key(node: dict) -> str:
    if node["resource_type"] == "source":
        return f"source.{node['source_name']}.{node['name']}"
    if node["resource_type"] == "exposure":
        # Exposures often share a name with the rpt_ model they read.
        return f"exposure.{node['name']}"
    return f"{node['package_name']}.{node['name']}"


def source_folder(node: dict, manifest: dict | None = None) -> str:
    """Top folder under models/ in kipptaf; else the package.

    A snapshot takes the folder of the model it snapshots (its yml stem when
    no manifest is given or it has no parent).
    """
    if node["package_name"] != "kipptaf":
        return node["package_name"]
    path = PurePosixPath(node["original_file_path"])
    if node["resource_type"] == "snapshot":
        parents = _parents(manifest, node) if manifest else []
        return source_folder(parents[0]) if parents else path.stem
    return path.parts[1]


def _lookup(manifest: dict, unique_id: str) -> dict | None:
    for key in ("nodes", "sources", "exposures"):
        if unique_id in manifest.get(key, {}):
            return manifest[key][unique_id]
    return None


def _parents(manifest: dict, node: dict) -> list[dict]:
    found = (_lookup(manifest, u) for u in node["depends_on"]["nodes"])
    return [p for p in found if p is not None]


def layer_of(node: dict, project: str, domain_folders: set[str]) -> str:
    """One of source, stg, source_int, domain_int, mart, rpt, snapshot, other."""
    if node["resource_type"] == "source":
        layer = _prefix_layer(node["identifier"])
        return (
            "source_int" if layer == "int" else layer if layer != "other" else "source"
        )
    if node["resource_type"] == "snapshot":
        return "snapshot"
    layer = _prefix_layer(node["name"])
    if layer != "int":
        return layer
    if project != "kipptaf":
        return "source_int"
    return "domain_int" if source_folder(node) in domain_folders else "source_int"


def _allowed(
    child: dict,
    child_layer: str,
    parent: dict,
    parent_layer: str,
    siblings: list[dict],
    project: str,
    manifest: dict,
) -> bool:
    if parent_layer == "other":
        return True
    # stg_ may read any source(), including a district stg_ it unions, but not
    # a district int_: that union belongs in a source int_
    if (
        child_layer == "stg"
        and parent["resource_type"] == "source"
        and parent_layer != "source_int"
    ):
        return True
    if child_layer == "rpt" and project != "kipptaf":
        reads_extracts = any(
            p["resource_type"] == "source" and p["source_name"] == "kipptaf_extracts"
            for p in siblings
        )
        if parent_layer == "rpt" and parent.get("source_name") == "kipptaf_extracts":
            return True
        if parent_layer == "stg" and reads_extracts:
            return True
    if parent_layer not in ALLOWED[child_layer]:
        return False
    if child_layer == "source_int" and parent["resource_type"] != "source":
        folder = source_folder(parent, manifest)
        return folder in _CONFIG_FOLDERS or folder == source_folder(child)
    return True


def check_edges(
    manifest: dict, project: str, domain_folders: set[str]
) -> list[Violation]:
    """A1 for every forbidden model edge, A8 for every forbidden exposure edge."""
    out = []
    for node in manifest.get("nodes", {}).values():
        if node["resource_type"] != "model" or not node["config"].get("enabled", True):
            continue
        layer = layer_of(node, project, domain_folders)
        if layer not in ALLOWED:
            continue
        parents = _parents(manifest, node)
        for parent in parents:
            p_layer = layer_of(parent, project, domain_folders)
            if not _allowed(node, layer, parent, p_layer, parents, project, manifest):
                out.append(_violation(node, "A1", parent, layer, p_layer))
    for exp in manifest.get("exposures", {}).values():
        kinds = (
            exp.get("config", {}).get("meta", {}).get("dagster", {}).get("kinds", [])
        )
        layer = "cube" if "cube" in kinds else "exposure"
        for parent in _parents(manifest, exp):
            p_layer = layer_of(parent, project, domain_folders)
            if p_layer != "other" and p_layer not in ALLOWED[layer]:
                out.append(_violation(exp, "A8", parent, layer, p_layer))
    return sorted(out, key=lambda v: (v.model, v.rule, v.detail))


def _violation(
    node: dict, rule: str, parent: dict, layer: str, p_layer: str
) -> Violation:
    child, detail = _key(node), _key(parent)
    return Violation(
        child, rule, detail, "error", f"{layer} {child} may not read {p_layer} {detail}"
    )


# Key macros in src/dbt/kipptaf/macros/entity_keys.sql (A7).
KEY_MACROS = {
    "student_key",
    "staff_key",
    "work_assignment_key",
    "region_key",
    "survey_key",
    "survey_question_key",
    "college_key",
    "job_candidate_key",
    "staff_observation_key",
    "staff_observation_rubric_key",
    "staff_observation_goal_type_key",
    "course_section_key",
    "course_key",
    "student_section_enrollment_key",
    "intervention_type_key",
    "behavioral_incident_key",
    "family_communication_key",
    "staff_observation_rubric_measurement_key",
    "job_posting_key",
    "student_day_key",
    "student_enrollment_key",
    "assessment_key",
    "term_key",
    "survey_administration_key",
    "assessment_administration_key",
}

# Near misses of the A3 reshape suffixes (_pivot, _unpivot, _rollup,
# _scaffold, _union).
_A3_NEAR_MISSES = (
    "_pivoted",
    "_unpivoted",
    "_rollups",
    "_rolled_up",
    "_scaffolding",
    "_unioned",
    "_unions",
)

# sqlfmt indents CTE bodies, so a select at column 0 is the final statement or
# one of its union branches.
_STAR_SELECT = re.compile(r"^select\s+(?:distinct\s+)?\*", re.M | re.I)
_DIRECT_HASH = re.compile(r"generate_surrogate_key\(.*?\)\s*-?\}\}", re.S)
# What can follow a hash before its alias: parentheses it sits inside, the
# alias, or a jinja call or clause keyword that means it has none.
_ALIAS_SCAN = re.compile(
    r"[(){]|\bas\s+(\w+)|\b(?:select|from|where|join|on|union|group|order|having)\b",
    re.I,
)


def _hash_aliases(code: str) -> list[tuple[int, int, str]]:
    """(start, end, alias) per direct hash; the alias is the first `as` outside
    any parentheses opened after the hash."""
    out = []
    for m in _DIRECT_HASH.finditer(code):
        depth = 0
        for t in _ALIAS_SCAN.finditer(code, m.end()):
            if t.group() == "(":
                depth += 1
            elif t.group() == ")":
                depth -= 1
            elif depth > 0:
                continue
            elif t.group(1):
                out.append((m.start(), t.end(), t.group(1)))
                break
            else:
                break
    return out


def _line(code: str, offset: int) -> int:
    return code.count("\n", 0, offset) + 1


# Keys a mart role-plays under a prefix (submitter_staff_key). Other entities
# carry suffix-alike keys of their own (grades_term_key is not term_key).
_ROLE_PLAYED = ("staff_key", "student_key")


def _macro_for(alias: str) -> str | None:
    if alias in KEY_MACROS:
        return alias
    for key in _ROLE_PLAYED:
        if alias.endswith("_" + key):
            return key
    return None


def _grains(manifest: dict) -> dict[str, set[frozenset[str]]]:
    out: dict[str, set[frozenset[str]]] = {}
    for test in manifest.get("nodes", {}).values():
        if test["resource_type"] != "test" or not test.get("attached_node"):
            continue
        meta = test.get("test_metadata") or {}
        if meta.get("name") == "unique" and test.get("column_name"):
            grain = frozenset([test["column_name"]])
        elif meta.get("name") == "unique_combination_of_columns":
            grain = frozenset(meta["kwargs"]["combination_of_columns"])
        else:
            continue
        out.setdefault(test["attached_node"], set()).add(grain)
    return out


@dataclass
class _Graph:
    grains: dict[str, set[frozenset[str]]]
    models: list[dict]
    children: dict[str, set[str]]


def _graph(manifest: dict) -> _Graph:
    models = [
        n
        for n in manifest["nodes"].values()
        if n["resource_type"] == "model" and n["config"].get("enabled", True)
    ]
    children: dict[str, set[str]] = {}
    for n in models:
        for p in n["depends_on"]["nodes"]:
            children.setdefault(p, set()).add(n["unique_id"])
    return _Graph(_grains(manifest), models, children)


def _a4(
    g: _Graph, node: dict, layer: str, domain_folders: set[str], project: str
) -> list[Violation]:
    grains, models, children = g.grains, g.models, g.children
    mine = grains.get(node["unique_id"], set())
    near = set(node["depends_on"]["nodes"]) | children.get(node["unique_id"], set())
    my_children = children.get(node["unique_id"], set())
    out = []
    for other in models:
        uid = other["unique_id"]
        if uid == node["unique_id"] or uid in near:
            continue
        if my_children & children.get(uid, set()):
            continue
        o_layer = layer_of(other, project, domain_folders)
        if o_layer != layer:
            continue
        if layer == "source_int" and source_folder(other) != source_folder(node):
            continue
        shared = mine & grains.get(uid, set())
        if shared:
            cols = ", ".join(sorted(next(iter(shared))))
            out.append(
                Violation(
                    _key(node),
                    "A4",
                    _key(other),
                    "warning",
                    f"{_key(node)} shares grain ({cols}) with {_key(other)}; extend it instead",
                )
            )
    return out


FileKey = tuple[str, str]


def _span(code: str, start: int, end: int) -> set[int]:
    return set(range(_line(code, start), _line(code, end) + 1))


def check_touched(
    manifest: dict,
    project: str,
    changed: dict[FileKey, set[int]],
    added: set[FileKey],
    domain_folders: set[str],
) -> list[Violation]:
    """A3/A4 on added intermediates; A7/A9 on changed lines of marts and rpt_.

    changed maps (package, package-relative path) to the line numbers the PR
    adds or changes; added holds the same keys for new files.
    """
    out = []
    graph = _graph(manifest) if added else None
    for node in manifest.get("nodes", {}).values():
        if node["resource_type"] != "model" or not node["config"].get("enabled", True):
            continue
        file_key = (node["package_name"], node["original_file_path"])
        if file_key not in changed:
            continue
        lines, code, key = changed[file_key], node.get("raw_code", ""), _key(node)
        layer = layer_of(node, project, domain_folders)
        found = []
        if layer in ("mart", "rpt") and any(
            _span(code, m.start(), m.end()) & lines for m in _STAR_SELECT.finditer(code)
        ):
            found.append(
                Violation(
                    key, "A9", "select *", "error", f"{key}: final select is select *"
                )
            )
        if layer == "mart":
            for start, end, alias in _hash_aliases(code):
                macro = _macro_for(alias)
                if macro and _span(code, start, end) & lines:
                    found.append(
                        Violation(
                            key,
                            "A7",
                            alias,
                            "error",
                            f"{key}: hash {alias} with {{{{ {macro}(...) }}}}, not generate_surrogate_key",
                        )
                    )
        if graph and layer in ("source_int", "domain_int") and file_key in added:
            if node["name"].endswith(_A3_NEAR_MISSES):
                found.append(
                    Violation(
                        key,
                        "A3",
                        node["name"],
                        "error",
                        f"{key}: reshape suffixes are _pivot, _unpivot, _rollup, _scaffold, _union",
                    )
                )
            found.extend(_a4(graph, node, layer, domain_folders, project))
        exempt = node["config"].get("meta", {}).get("standard_exempt") or {}
        out.extend(v for v in found if v.rule not in exempt)
    return sorted(out, key=lambda v: (v.model, v.rule, v.detail))


Key = tuple[str, str, str]


def load_baseline(path: Path) -> dict[Key, str]:
    """TSV model, rule, detail, issue (header row first) -> {key: issue}."""
    out = {}
    with open(path, newline="") as f:
        rows = csv.reader(f, delimiter="\t")
        next(rows, None)
        for row in rows:
            if not row:
                continue
            row += [""] * (4 - len(row))
            out[(row[0], row[1], row[2])] = row[3].strip()
    return out


_ISSUE = re.compile(r"#\d+")


def compare(
    violations: list[Violation], baseline: dict[Key, str]
) -> tuple[list[Violation], list[Key], list[Key]]:
    """(violations not in the baseline, baseline lines no longer found, lines whose
    issue cell is not #N)."""
    keys = {(v.model, v.rule, v.detail) for v in violations}
    new = [v for v in violations if (v.model, v.rule, v.detail) not in baseline]
    stale = sorted(k for k in baseline if k not in keys)
    missing = sorted(k for k, issue in baseline.items() if not _ISSUE.fullmatch(issue))
    return new, stale, missing


def closed_issues(
    baseline: dict[Key, str], is_open: Callable[[int], bool]
) -> list[tuple[str, int]]:
    """(issue, row count) for each baseline issue that is_open says is closed."""
    rows = Counter(i for i in baseline.values() if _ISSUE.fullmatch(i))
    return sorted(
        (issue, n) for issue, n in rows.items() if not is_open(int(issue.lstrip("#")))
    )


def _gh_issue_open(number: int) -> bool:
    # trunk-ignore(bandit/B603): hardcoded gh command, no user input
    is_open = subprocess.run(
        ["gh", "api", f"repos/{os.environ['GITHUB_REPOSITORY']}/issues/{number}"]
        # a PR number resolves here too; it tracks nothing, so it is not open
        + ["--jq", '.pull_request == null and .state == "open"'],
        stdout=subprocess.PIPE,  # stderr reaches the job log on failure
        text=True,
        check=True,
    ).stdout.strip()
    return is_open == "true"


def package_roots(project_dir: Path) -> dict[str, str]:
    """Every dbt project beside project_dir, by folder name (each folder is
    named for its package), as a path relative to the working directory: the
    repo root, where git diff paths start."""
    base = project_dir.resolve().parent
    return {
        d.name: os.path.relpath(d, Path.cwd())
        for d in sorted(base.iterdir())
        if (d / "dbt_project.yml").exists()
    }


def _file_key(target: str, roots: dict[str, str]) -> FileKey | None:
    for package, root in roots.items():
        if target.startswith(root + "/"):
            return package, target[len(root) + 1 :]
    return None


def parse_diff(
    diff: str, roots: dict[str, str]
) -> tuple[dict[FileKey, set[int]], set[FileKey]]:
    """Changed new-file line numbers and added files under roots, from git diff -U0."""
    changed: dict[FileKey, set[int]] = {}
    added: set[FileKey] = set()
    path, is_new, in_hunk, line = None, False, False, 0
    for raw in diff.splitlines():
        if raw.startswith("diff --git"):
            path, is_new, in_hunk = None, False, False
        elif in_hunk and raw.startswith("+"):
            if path:
                changed.setdefault(path, set()).add(line)
            line += 1
        elif raw.startswith("@@"):
            in_hunk = True
            hunk = re.match(r"@@ -\S+ \+(\d+)", raw)
            line = int(hunk.group(1)) if hunk else 0
        elif in_hunk:
            continue  # a removed line or "\ No newline at end of file"
        elif raw.startswith("new file mode"):
            is_new = True
        elif raw.startswith("+++ "):
            path = _file_key(raw[4:].removeprefix("b/"), roots)
            if path and is_new:
                added.add(path)
    return changed, added


def _write_baseline(
    path: Path, violations: list[Violation], old: dict[Key, str]
) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["model", "rule", "detail", "issue"])
        for k in sorted({(v.model, v.rule, v.detail) for v in violations}):
            w.writerow([*k, old.get(k, "")])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument(
        "--manifest", help="default: <project-dir>/target/manifest.json"
    )
    parser.add_argument(
        "--diff", help="git diff -U0 output; enables the changed-line rules"
    )
    parser.add_argument(
        "--baseline", help="default: <project-dir>/standard-baseline.tsv"
    )
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument(
        "--check-issues",
        action="store_true",
        help="fail on a baseline issue that is closed (needs gh and GITHUB_REPOSITORY)",
    )
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir)
    project = project_dir.name
    manifest = json.loads(
        Path(args.manifest or project_dir / "target/manifest.json").read_text()
    )
    baseline_path = Path(args.baseline or project_dir / "standard-baseline.tsv")

    exempt = exempt_index(manifest)
    edges = [
        v
        for v in check_edges(manifest, project, DOMAIN_FOLDERS)
        if v.rule not in exempt.get(v.model, {})
    ]
    baseline = load_baseline(baseline_path) if baseline_path.exists() else {}
    if args.write_baseline:
        _write_baseline(baseline_path, edges, baseline)
        print(f"wrote {len(edges)} lines to {baseline_path}")
        return 0

    new, stale, missing = compare(edges, baseline)
    touched = []
    if args.diff:
        changed, added = parse_diff(
            Path(args.diff).read_text(), package_roots(project_dir)
        )
        touched = check_touched(manifest, project, changed, added, DOMAIN_FOLDERS)

    for v in [*new, *touched]:
        print(f"::{v.severity} title={v.rule}::{v.message}")
    for k in stale:
        print(
            f"::error title=baseline::{baseline_path}: {' '.join(k)} no longer occurs; delete the line"
        )
    for k in missing:
        print(
            f"::error title=baseline::{baseline_path}: {' '.join(k)} has no tracking issue (#N)"
        )
    # A closed issue leaves its rows tracked by nothing. It fails whichever PR runs
    # next, so the message says the PR did not cause it.
    closed = closed_issues(baseline, _gh_issue_open) if args.check_issues else []
    for issue, n in closed:
        print(
            f"::error title=baseline::{baseline_path}: {issue} is closed but {n} rows point at it. This PR did not cause it: reopen the issue or point the rows at an open one, then rerun this job"
        )
    failed = (
        any(v.severity == "error" for v in [*new, *touched])
        or stale
        or missing
        or closed
    )
    return 1 if failed else 0


def exempt_index(manifest: dict) -> dict[str, dict]:
    """standard_exempt per model and exposure, by violation key."""
    return {
        _key(n): n.get("config", {}).get("meta", {}).get("standard_exempt") or {}
        for coll in ("nodes", "exposures")
        for n in manifest.get(coll, {}).values()
        if n["resource_type"] in ("model", "exposure")
    }


if __name__ == "__main__":
    sys.exit(main())
