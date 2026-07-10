"""Cube schema invariants — cube/view names carry no warehouse prefix."""

import pathlib

import yaml

CUBE_MODEL_DIR = pathlib.Path(__file__).parents[2] / "src" / "cube" / "model"


def _names() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in CUBE_MODEL_DIR.rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for kind in ("cubes", "views"):
            for obj in doc.get(kind, []) or []:
                found.append((str(path), obj["name"]))
    return found


def test_no_dim_or_fct_prefix_on_cube_names() -> None:
    offenders = [
        f"{path}: {name}"
        for path, name in _names()
        if name.startswith(("dim_", "fct_"))
    ]
    assert not offenders, (
        "cube/view names must not carry a dim_/fct_ prefix:\n" + "\n".join(offenders)
    )


def test_model_dir_has_cubes() -> None:
    # Guard against a path regression silently passing the prefix test.
    assert _names(), f"no cubes/views found under {CUBE_MODEL_DIR}"


def _access_policy_groups() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in CUBE_MODEL_DIR.rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for obj in doc.get("views", []) or []:
            for policy in obj.get("access_policy", []) or []:
                group = policy.get("group")
                if group is not None:
                    found.append((str(path), group))
    return found


def test_no_retired_cube_access_group_prefix() -> None:
    # The access_policy pivot retired the cube-access-* group names in favor of
    # student-*/staff-* scope groups; guard against a regression back to them.
    offenders = [
        f"{path}: {group}"
        for path, group in _access_policy_groups()
        if group.startswith("cube-access-")
    ]
    assert not offenders, (
        "access_policy groups must not use the retired cube-access- prefix:\n"
        + "\n".join(offenders)
    )


def test_views_declare_access_policies() -> None:
    # RLS lives entirely in access_policy now; a view losing its policy block
    # would silently default-open. Guard against the group set going empty.
    assert _access_policy_groups(), "no access_policy groups found under views"
