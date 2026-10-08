"""Check dbt models against the architecture rules in .claude/rules/dbt-architecture.md.

Reads a dbt manifest and reports layer edges the Allowed edges table forbids
(A1) and exposures that read below the consumer layer (A8).
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
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
