"""Check dbt models against the architecture rules in .claude/rules/dbt-architecture.md.

Usage: uv run scripts/check_dbt_standard.py --project-dir src/dbt/<project>
    [--diff <git diff -U0 file>] [--write-baseline]

Edge rules (A1, A8) run over the whole manifest against a per-project baseline
of known violations; a baseline line must name a tracking issue and is removed
once fixed. Changed-line rules (A3, A4, A7, A9) need --diff. A model opts out
of a rule with config.meta.standard_exempt: {<rule>: <reason>}.
"""

import argparse
import csv
import json
import re
import sys
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

# Config inputs, not a second source system (interim domain test).
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
    return f"{node['package_name']}.{node['name']}"


def source_folder(node: dict) -> str:
    """Top folder under models/ (snapshots: the yml stem) in kipptaf; else the package."""
    if node["package_name"] != "kipptaf":
        return node["package_name"]
    path = PurePosixPath(node["original_file_path"])
    if node["resource_type"] == "snapshot":
        return path.stem
    return path.parts[1]


def _lookup(manifest: dict, unique_id: str) -> dict | None:
    for key in ("nodes", "sources", "exposures"):
        if unique_id in manifest.get(key, {}):
            return manifest[key][unique_id]
    return None


def _parents(manifest: dict, node: dict) -> list[dict]:
    found = (_lookup(manifest, u) for u in node["depends_on"]["nodes"])
    return [p for p in found if p is not None]


def layer_of(node: dict, manifest: dict, project: str, domain_folders: set[str]) -> str:
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
    if source_folder(node) in domain_folders:
        return "domain_int"
    folders = {
        source_folder(p)
        for p in _parents(manifest, node)
        if p["resource_type"] != "source"
    }
    return "domain_int" if len(folders - _CONFIG_FOLDERS) > 1 else "source_int"


def _allowed(
    child: dict,
    child_layer: str,
    parent: dict,
    parent_layer: str,
    siblings: list[dict],
    project: str,
) -> bool:
    if parent_layer == "other":
        return True
    # stg_ may read any source(), including a district stg_ it unions
    if child_layer == "stg" and parent["resource_type"] == "source":
        return True
    if child_layer == "rpt" and project != "kipptaf":
        reads_extracts = any(
            p["resource_type"] == "source" and p["source_name"] == "kipptaf_extracts"
            for p in siblings
        )
        if parent_layer == "rpt" and parent["resource_type"] == "source":
            return True
        if parent_layer == "stg" and reads_extracts:
            return True
    if parent_layer not in ALLOWED[child_layer]:
        return False
    if child_layer == "source_int" and parent["resource_type"] != "source":
        folder = source_folder(parent)
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
        layer = layer_of(node, manifest, project, domain_folders)
        if layer not in ALLOWED:
            continue
        parents = _parents(manifest, node)
        for parent in parents:
            p_layer = layer_of(parent, manifest, project, domain_folders)
            if not _allowed(node, layer, parent, p_layer, parents, project):
                out.append(_violation(node, "A1", parent, layer, p_layer))
    for exp in manifest.get("exposures", {}).values():
        kinds = (
            exp.get("config", {}).get("meta", {}).get("dagster", {}).get("kinds", [])
        )
        layer = "cube" if "cube" in kinds else "exposure"
        for parent in _parents(manifest, exp):
            p_layer = layer_of(parent, manifest, project, domain_folders)
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

_FINAL_SELECT = re.compile(r"^select\b", re.M)
# a direct hash up to its alias, never crossing into the next {{ }} call
_DIRECT_HASH = re.compile(
    r"generate_surrogate_key\(.*?\)\s*-?\}\}[^{]{0,200}?\bas\s+(\w+_key)\b", re.S
)


def _line(code: str, offset: int) -> int:
    return code.count("\n", 0, offset) + 1


def _macro_for(alias: str) -> str | None:
    for key in KEY_MACROS:
        if alias == key or alias.endswith("_" + key):
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


def _a4(
    manifest: dict, node: dict, layer: str, domain_folders: set[str], project: str
) -> list[Violation]:
    grains = _grains(manifest)
    mine = grains.get(node["unique_id"], set())
    models = [
        n
        for n in manifest["nodes"].values()
        if n["resource_type"] == "model" and n["config"].get("enabled", True)
    ]
    children: dict[str, set[str]] = {}
    for n in models:
        for p in n["depends_on"]["nodes"]:
            children.setdefault(p, set()).add(n["unique_id"])
    near = set(node["depends_on"]["nodes"]) | children.get(node["unique_id"], set())
    my_children = children.get(node["unique_id"], set())
    out = []
    for other in models:
        uid = other["unique_id"]
        if uid == node["unique_id"] or uid in near:
            continue
        if my_children & children.get(uid, set()):
            continue
        o_layer = layer_of(other, manifest, project, domain_folders)
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


def check_touched(
    manifest: dict,
    project: str,
    changed: dict[str, set[int]],
    added: set[str],
    domain_folders: set[str],
) -> list[Violation]:
    """A3/A4 on added intermediates; A7/A9 on changed lines of marts and rpt_.

    changed maps a project-relative path to the line numbers the PR adds or
    changes; added holds the project-relative paths of new files.
    """
    out = []
    for node in manifest.get("nodes", {}).values():
        if node["resource_type"] != "model" or not node["config"].get("enabled", True):
            continue
        path = node["original_file_path"]
        if node["package_name"] != project or path not in changed:
            continue
        lines, code, key = changed[path], node.get("raw_code", ""), _key(node)
        layer = layer_of(node, manifest, project, domain_folders)
        found = []
        if layer in ("mart", "rpt"):
            selects = list(_FINAL_SELECT.finditer(code))
            if selects:
                last = selects[-1]
                if (
                    re.match(r"select\s+\*", code[last.start() :])
                    and _line(code, last.start()) in lines
                ):
                    found.append(
                        Violation(
                            key,
                            "A9",
                            "select *",
                            "error",
                            f"{key}: final select is select *",
                        )
                    )
        if layer == "mart":
            for m in _DIRECT_HASH.finditer(code):
                macro = _macro_for(m.group(1))
                span = set(range(_line(code, m.start()), _line(code, m.end()) + 1))
                if macro and span & lines:
                    found.append(
                        Violation(
                            key,
                            "A7",
                            m.group(1),
                            "error",
                            f"{key}: hash {m.group(1)} with {{{{ {macro}(...) }}}}, not generate_surrogate_key",
                        )
                    )
        if layer in ("source_int", "domain_int") and path in added:
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
            found.extend(_a4(manifest, node, layer, domain_folders, project))
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
            row += [""] * (4 - len(row))
            out[(row[0], row[1], row[2])] = row[3].strip()
    return out


def compare(
    violations: list[Violation], baseline: dict[Key, str]
) -> tuple[list[Violation], list[Key], list[Key]]:
    """(violations not in the baseline, baseline lines no longer found, lines without an issue)."""
    keys = {(v.model, v.rule, v.detail) for v in violations}
    new = [v for v in violations if (v.model, v.rule, v.detail) not in baseline]
    stale = sorted(k for k in baseline if k not in keys)
    missing = sorted(k for k, issue in baseline.items() if not issue)
    return new, stale, missing


def parse_diff(diff: str, project_dir: str) -> tuple[dict[str, set[int]], set[str]]:
    """Changed new-file line numbers and added files under project_dir, from git diff -U0."""
    prefix = project_dir.strip("/").removeprefix("./") + "/"
    changed: dict[str, set[int]] = {}
    added: set[str] = set()
    path, is_new, line = None, False, 0
    for raw in diff.splitlines():
        if raw.startswith("diff --git"):
            path, is_new = None, False
        elif raw.startswith("new file mode"):
            is_new = True
        elif raw.startswith("+++ "):
            target = raw[4:].removeprefix("b/")
            path = target[len(prefix) :] if target.startswith(prefix) else None
            if path and is_new:
                added.add(path)
        elif raw.startswith("@@") and path:
            hunk = re.match(r"@@ -\S+ \+(\d+)", raw)
            line = int(hunk.group(1)) if hunk else 0
        elif raw.startswith("+") and path:
            changed.setdefault(path, set()).add(line)
            line += 1
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
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir)
    project = project_dir.name
    manifest = json.loads(
        Path(args.manifest or project_dir / "target/manifest.json").read_text()
    )
    baseline_path = Path(args.baseline or project_dir / "standard-baseline.tsv")
    domain_folders = {
        source_folder(n)
        for n in manifest["nodes"].values()
        if n["resource_type"] == "model"
        and n["package_name"] == "kipptaf"
        and n["config"].get("meta", {}).get("layer") == "domain"
    }

    edges = [
        v
        for v in check_edges(manifest, project, domain_folders)
        if v.rule not in _exempt_rules(manifest, v.model)
    ]
    baseline = load_baseline(baseline_path) if baseline_path.exists() else {}
    if args.write_baseline:
        _write_baseline(baseline_path, edges, baseline)
        print(f"wrote {len(edges)} lines to {baseline_path}")
        return 0

    new, stale, missing = compare(edges, baseline)
    touched = []
    if args.diff:
        changed, added = parse_diff(Path(args.diff).read_text(), args.project_dir)
        touched = check_touched(manifest, project, changed, added, domain_folders)

    for v in [*new, *touched]:
        print(f"::{v.severity} title={v.rule}::{v.message}")
    for k in stale:
        print(
            f"::error title=baseline::{baseline_path}: {' '.join(k)} no longer occurs; delete the line"
        )
    for k in missing:
        print(
            f"::error title=baseline::{baseline_path}: {' '.join(k)} has no tracking issue"
        )
    failed = any(v.severity == "error" for v in [*new, *touched]) or stale or missing
    return 1 if failed else 0


def _exempt_rules(manifest: dict, key: str) -> dict:
    package, _, name = key.partition(".")
    for coll in ("nodes", "exposures"):
        for n in manifest.get(coll, {}).values():
            if n.get("package_name") == package and n.get("name") == name:
                return n.get("config", {}).get("meta", {}).get("standard_exempt") or {}
    return {}


if __name__ == "__main__":
    sys.exit(main())
