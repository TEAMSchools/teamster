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


def _filter_members(filters: list[dict]) -> list[str]:
    # row_level filters can nest boolean combinators (Cube's accessPolicy
    # schema) -- walk "or"/"and" branches too, not just the top-level list.
    members = []
    for f in filters:
        if "member" in f:
            members.append(f["member"])
        for combinator in ("or", "and"):
            if combinator in f:
                members.extend(_filter_members(f[combinator]))
    return members


def _view_exposed_members(view_doc: dict) -> set[str]:
    # Reconstructs the flat member names a view actually exposes, the same
    # way Cube does: prefix: true -> "<lastJoinPathSegment>_<member>",
    # else bare (see src/cube/CLAUDE.md "row_level.filters[].member is a
    # flat view-member name, not a cube-qualified path").
    exposed: set[str] = set()
    for cube_ref in view_doc.get("cubes", []) or []:
        join_cube = cube_ref["join_path"].split(".")[-1]
        prefixed = cube_ref.get("prefix", False)
        for member in cube_ref.get("includes", []) or []:
            exposed.add(f"{join_cube}_{member}" if prefixed else member)
    return exposed


def test_row_level_filter_members_are_exposed_by_their_view() -> None:
    # A row_level filter naming a member the view doesn't (or no longer)
    # expose compiles fine but silently never matches -- Cube has no
    # standalone error for it (this is the same prefix/bare divergence
    # documented in src/cube/CLAUDE.md).
    offenders = []
    for path in CUBE_MODEL_DIR.rglob("views/**/*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []) or []:
            exposed = _view_exposed_members(view)
            for policy in view.get("access_policy", []) or []:
                filters = policy.get("row_level", {}).get("filters", []) or []
                for member in _filter_members(filters):
                    if member not in exposed:
                        offenders.append(
                            f"{path}: view {view['name']!r} group "
                            f"{policy.get('group')!r} row_level member "
                            f"{member!r} is not exposed by this view"
                        )
    assert not offenders, (
        "row_level filter references a member the view doesn't expose:\n"
        + "\n".join(offenders)
    )
