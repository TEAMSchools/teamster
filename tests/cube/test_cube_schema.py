"""Cube schema invariants — cube/view names carry no warehouse prefix."""

import functools
import json
import pathlib
import re
import shutil
import subprocess

import pytest
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


def _pre_aggregations_by_root_cube() -> dict[str, list[dict]]:
    # Keyed by the fact cube the pre-aggregation is declared on.
    found: dict[str, list[dict]] = {}
    for path in CUBE_MODEL_DIR.rglob("cubes/**/*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for cube in doc.get("cubes", []) or []:
            pre_aggs = cube.get("pre_aggregations", []) or []
            if pre_aggs:
                found[cube["name"]] = pre_aggs
    return found


def _filter_members(filters: list[dict]) -> list[str]:
    # row_level filters can nest boolean combinators (Cube's accessPolicy
    # schema) — walk "or"/"and" branches too, not just the top-level list.
    members = []
    for f in filters:
        if "member" in f:
            members.append(f["member"])
        for combinator in ("or", "and"):
            if combinator in f:
                members.extend(_filter_members(f[combinator]))
    return members


def _include_name(include: str | dict) -> str:
    # An includes entry is a member name, or an object ({name, meta, ...})
    # when the view overrides that member's meta.
    return include["name"] if isinstance(include, dict) else include


def _view_member_to_qualified_name(view_doc: dict) -> dict[str, str]:
    # Maps each member name exposed by this view back to its cube-qualified
    # name, honoring each includes block's prefix: setting (see
    # src/cube/CLAUDE.md "row_level.filters[].member is a flat view-member
    # name" -- prefix: true -> "<lastJoinPathSegment>_<member>", else bare).
    mapping: dict[str, str] = {}
    for cube_ref in view_doc.get("cubes", []) or []:
        join_cube = cube_ref["join_path"].split(".")[-1]
        prefixed = cube_ref.get("prefix", False)
        for member in map(_include_name, cube_ref.get("includes", []) or []):
            exposed = f"{join_cube}_{member}" if prefixed else member
            mapping[exposed] = f"{join_cube}.{member}"
    return mapping


def _view_exposed_members(view_doc: dict) -> set[str]:
    # Reconstructs the flat member names a view actually exposes, the same
    # way Cube does: prefix: true -> "<lastJoinPathSegment>_<member>",
    # else bare (see src/cube/CLAUDE.md "row_level.filters[].member is a
    # flat view-member name, not a cube-qualified path").
    exposed: set[str] = set()
    for cube_ref in view_doc.get("cubes", []) or []:
        join_cube = cube_ref["join_path"].split(".")[-1]
        prefixed = cube_ref.get("prefix", False)
        for member in map(_include_name, cube_ref.get("includes", []) or []):
            exposed.add(f"{join_cube}_{member}" if prefixed else member)
    return exposed


def _root_cube(view_doc: dict) -> str | None:
    cube_refs = view_doc.get("cubes", []) or []
    if not cube_refs:
        return None
    return cube_refs[0]["join_path"].split(".")[0]


def test_pre_aggregation_covers_row_level_scoping_members() -> None:
    # A row_level scoping member added to a view's access_policy without a
    # matching addition to that fact's pre-aggregation dimensions silently
    # drops scoped viewers back to the slow fact-scan path -- no error, no
    # test failure otherwise.
    pre_aggs_by_cube = _pre_aggregations_by_root_cube()
    offenders = []
    for path in CUBE_MODEL_DIR.rglob("views/**/*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []) or []:
            root = _root_cube(view)
            if root not in pre_aggs_by_cube:
                continue

            member_map = _view_member_to_qualified_name(view)
            filter_members = [
                member
                for policy in view.get("access_policy", []) or []
                for member in _filter_members(
                    policy.get("row_level", {}).get("filters", []) or []
                )
            ]

            for pre_agg in pre_aggs_by_cube[root]:
                rollup_dims = set(pre_agg.get("dimensions", []) or [])
                for filter_member in filter_members:
                    qualified = member_map.get(filter_member)
                    if qualified is not None and qualified not in rollup_dims:
                        offenders.append(
                            f"{path}: view {view['name']!r} row_level member "
                            f"{filter_member!r} ({qualified}) is not in "
                            f"{root}.{pre_agg['name']}'s dimensions"
                        )
    assert not offenders, (
        "pre-aggregation missing a dimension its own view scopes row_level on:\n"
        + "\n".join(offenders)
    )


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


REPO_ROOT = pathlib.Path(__file__).parents[2]
DBT_MODELS_DIR = REPO_ROOT / "src" / "dbt" / "kipptaf" / "models"
AI_CONTEXT_MAX = 2000

# (cube, member) -> (dbt model, column). A Cube member that reads one column
# directly carries the same description as that column in dbt.
TWINS: dict[tuple[str, str], tuple[str, str]] = {}

# "<cube>.<member>" or "<view>" -> phrases that must appear in that member's
# description or ai_context (case-insensitive, whitespace-collapsed), so a later
# edit cannot drop a moved fact silently.
PHRASES: dict[str, list[str]] = {}


def _norm(text: str | None) -> str:
    return " ".join((text or "").split())


def _cube_docs() -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for path in (CUBE_MODEL_DIR / "cubes").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for cube in doc.get("cubes", []):
            docs[cube["name"]] = cube
    return docs


def _view_docs() -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for path in (CUBE_MODEL_DIR / "views").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []):
            docs[view["name"]] = view
    return docs


def _members(cube: dict) -> dict[str, dict]:
    return {m["name"]: m for m in cube.get("dimensions", []) + cube.get("measures", [])}


def _resolve_member(cubes: dict[str, dict], cube_name: str, member: str) -> dict | None:
    """Find a member on a cube, following `extends` (staff_lead_teacher)."""
    cube = cubes.get(cube_name)
    while cube is not None:
        found = _members(cube).get(member)
        if found is not None:
            return found
        parent = cube.get("extends")
        cube = cubes.get(parent) if parent else None
    return None


@functools.cache
def _dbt_columns() -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for path in DBT_MODELS_DIR.rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for m in doc.get("models", []) or []:
            for c in m.get("columns", []) or []:
                index[(m["name"], c["name"])] = c
    return index


def _dbt_column(model: str, column: str) -> dict:
    found = _dbt_columns().get((model, column))
    assert found is not None, f"dbt column {model}.{column} not found"
    return found


def _view_override_texts(view: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for block in view.get("cubes", []):
        for inc in block.get("includes", []) or []:
            if isinstance(inc, dict):
                text = (inc.get("meta") or {}).get("ai_context")
                if text:
                    out.append((inc["name"], text))
    return out


def _ai_contexts() -> list[tuple[str, str]]:
    """Every ai_context in the model: cube members, views, view overrides."""
    out: list[tuple[str, str]] = []
    for name, cube in _cube_docs().items():
        for m in _members(cube).values():
            text = (m.get("meta") or {}).get("ai_context")
            if text:
                out.append((f"{name}.{m['name']}", text))
    for name, view in _view_docs().items():
        text = (view.get("meta") or {}).get("ai_context")
        if text:
            out.append((name, text))
        out += [(f"{name}:{member}", t) for member, t in _view_override_texts(view)]
    return out


def test_moved_facts_keep_their_key_phrases() -> None:
    cubes, views = _cube_docs(), _view_docs()
    missing: list[str] = []
    for key, phrases in PHRASES.items():
        if key in views:
            view = views[key]
            parts = [
                view.get("description"),
                (view.get("meta") or {}).get("ai_context"),
            ]
            parts += [t for _, t in _view_override_texts(view)]
        else:
            cube_name, member_name = key.split(".", 1)
            member = _resolve_member(cubes, cube_name, member_name)
            assert member is not None, f"{key}: member not found"
            parts = [
                member.get("description"),
                (member.get("meta") or {}).get("ai_context"),
            ]
        text = " ".join(_norm(p) for p in parts).lower()
        missing += [f"{key}: {p!r}" for p in phrases if _norm(p).lower() not in text]
    assert not missing, "moved facts missing:\n" + "\n".join(missing)


_ONE_COLUMN = re.compile(r"^\s*(?:\{CUBE\}\.)?`?(\w+)`?\s*$")


def test_twinned_members_match_their_dbt_description() -> None:
    cubes = _cube_docs()
    mismatches: list[str] = []
    for (cube_name, member_name), (model, column) in TWINS.items():
        member = _members(cubes[cube_name])[member_name]
        read = _ONE_COLUMN.match(str(member.get("sql", "")))
        assert read and read.group(1) == column, (
            f"{cube_name}.{member_name} does not read {column} directly"
        )
        cube_text = _norm(member.get("description"))
        dbt_text = _norm(_dbt_column(model, column).get("description"))
        if cube_text != dbt_text:
            mismatches.append(
                f"{cube_name}.{member_name} vs {model}.{column}:\n"
                f"  cube: {cube_text}\n  dbt:  {dbt_text}"
            )
    assert not mismatches, "\n".join(mismatches)


def test_ai_context_fits_the_cap() -> None:
    too_long = [
        f"{key}: {len(text)} chars"
        for key, text in _ai_contexts()
        if len(text) > AI_CONTEXT_MAX
    ]
    assert not too_long, (
        f"ai_context over {AI_CONTEXT_MAX} chars (Cube truncates silently):\n"
        + "\n".join(too_long)
    )


def test_view_overrides_do_not_hide_cube_ai_context() -> None:
    """An include-level override replaces the member's whole meta in that view,
    so it must restate any ai_context the cube member already carries."""
    cubes = _cube_docs()
    hidden: list[str] = []
    for view_name, view in _view_docs().items():
        for block in view.get("cubes", []):
            cube_name = str(block["join_path"]).split(".")[-1].strip()
            for inc in block.get("includes", []) or []:
                if not isinstance(inc, dict) or "meta" not in inc:
                    continue
                member = _resolve_member(cubes, cube_name, inc["name"])
                assert member is not None, (
                    f"{view_name}: override on {cube_name}.{inc['name']} "
                    "matches no member"
                )
                base = _norm((member.get("meta") or {}).get("ai_context"))
                override = _norm((inc.get("meta") or {}).get("ai_context"))
                if base and base not in override:
                    hidden.append(f"{view_name}: {cube_name}.{inc['name']}")
    assert not hidden, "overrides hide a cube-level ai_context:\n" + "\n".join(hidden)


def _exposed_name(block: dict, member: str) -> str:
    if block.get("prefix"):
        return f"{str(block['join_path']).split('.')[-1].strip()}_{member}"
    return member


def test_grade_band_points_to_grade_level_only_where_it_exists() -> None:
    """locations is shared with staff_directory, which has no grade_level, so
    the pointer lives in per-view overrides, not on the cube member."""
    cubes = _cube_docs()
    base = _norm(
        (_members(cubes["locations"])["grade_band"].get("meta") or {}).get("ai_context")
    )
    wrong: list[str] = []
    for view_name, view in _view_docs().items():
        names = {_include_name(i) for b in view.get("cubes", []) for i in b["includes"]}
        for block in view.get("cubes", []):
            if not str(block["join_path"]).strip().endswith("locations"):
                continue
            for inc in block["includes"]:
                if _include_name(inc) != "grade_band":
                    continue
                text = base
                if isinstance(inc, dict) and "meta" in inc:
                    text = _norm(inc["meta"].get("ai_context"))
                if ("grade_level" in names) != ("use grade_level" in text):
                    wrong.append(view_name)
    assert not wrong, "grade_band pointer to grade_level is wrong in: " + ", ".join(
        wrong
    )


_COMPILER = (
    REPO_ROOT / "src" / "cube" / "node_modules" / "@cubejs-backend" / "schema-compiler"
)


@pytest.mark.skipif(
    not _COMPILER.exists() or shutil.which("node") is None,
    reason="Cube node_modules not installed (npm ci in src/cube)",
)
def test_model_compiles_with_cube() -> None:
    out = subprocess.run(
        [
            "node",
            str(REPO_ROOT / "src" / "cube" / "compile-meta.js"),
            str(CUBE_MODEL_DIR),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    compiled = {c["name"]: c for c in json.loads(out.stdout)["cubes"]}
    assert "student_assessment_scores_view" in compiled

    # Every YAML override must land on its member as aiContext, the key REST
    # /meta serves overrides under.
    misplaced: list[str] = []
    for view_name, view in _view_docs().items():
        members = {
            m["name"]: m
            for m in compiled[view_name]["dimensions"] + compiled[view_name]["measures"]
        }
        for block in view.get("cubes", []):
            for inc in block.get("includes", []) or []:
                if not isinstance(inc, dict) or "meta" not in inc:
                    continue
                name = f"{view_name}.{_exposed_name(block, inc['name'])}"
                got = (members.get(name, {}).get("meta") or {}).get("aiContext")
                if _norm(got) != _norm(inc["meta"].get("ai_context")):
                    misplaced.append(name)
    assert not misplaced, "overrides not served as aiContext:\n" + "\n".join(misplaced)


_SCORES_FACT = "fct_assessment_scores_enrollment_scoped"

TWINS.update(
    {
        **{
            ("student_assessment_scores", c): (_SCORES_FACT, c)
            for c in [
                "response_type",
                "response_type_code",
                "response_type_description",
                "response_type_root_description",
                "performance_band_label_number",
                "proficiency_level",
                "is_mastery",
                "scale_score",
                "percent_correct",
                "is_replacement",
                "enrollment_resolution",
            ]
        },
        ("student_assessments", "assessment_type"): ("dim_assessments", "type"),
        **{
            ("student_assessments", c): ("dim_assessments", c)
            for c in [
                "is_internal_assessment",
                "module_type",
                "module_code",
                "academic_subject",
                "grade_level_tested",
            ]
        },
        ("student_assessment_administrations", "administration_period"): (
            "dim_assessment_administrations",
            "administration_period",
        ),
        ("student_assessment_administrations", "source_assessment_id"): (
            "dim_assessment_administrations",
            "source_assessment_id",
        ),
        ("locations", "grade_band"): ("dim_locations", "grade_band"),
        ("courses", "is_foundations"): ("dim_courses", "is_foundations"),
    }
)

PHRASES.update(
    {
        # Scores cube dimensions
        "student_assessment_scores.response_type": [
            "not_taken",
            "strand or domain rollup",
            "Not additive across values",
            "default to overall",
        ],
        "student_assessment_scores.response_type_code": [
            "8.EE.C.8b",
            "an empty string, not null",
            "never average",
            "group on response_type_description",
        ],
        "student_assessment_scores.response_type_description": ["whitespace variants"],
        "student_assessment_scores.response_type_root_description": [
            "Florida's own standards",
            "resolve a parent standard",
        ],
        "student_assessment_scores.performance_band_label_number": [
            "Illuminate only; null for every other source",
            "Not comparable across assessments",
            "across response types",
        ],
        "student_assessment_scores.proficiency_level": [
            "Tested Out",
            "Graduation Ready",
            "Tier-movement rates are not comparable",
            "filter it with notSet",
            "no verdict nearly all carry Tested Out",
        ],
        "student_assessment_scores.is_mastery": [
            "Early On is a looser bar",
            "Illuminate rate mixes different bars",
            "Mid or Above Grade Level instead",
        ],
        "student_assessment_scores.scale_score": [
            "compresses at higher grades",
            "not a percent of the BOY score",
        ],
        "student_assessment_scores.percent_correct": [
            "Illuminate only; null for every other source",
        ],
        "student_assessment_scores.is_replacement": ["i-Ready, DIBELS and STAR"],
        "student_assessment_scores.enrollment_resolution": [
            "active on the test date",
            "Filter to subject_section",
        ],
        "student_assessment_scores.date_taken": [
            "date_day and academic_year",
            "not to find the most recent diagnostic",
        ],
        # Scores cube measures
        "student_assessment_scores.count_assigned": [
            "widest of 3 nested counts",
            "use count_taken",
        ],
        "student_assessment_scores.count_taken": [
            "DIBELS Tested Out subtests",
            "how many assessments were taken",
        ],
        "student_assessment_scores.count_scored": [
            "denominator of pct_proficient",
            "the n the rate rests on",
        ],
        "student_assessment_scores.count_proficient": [
            "numerator of pct_proficient",
            "how many were proficient",
        ],
        "student_assessment_scores.pct_taken": [
            "meaningful only within Illuminate",
            "Filter assessment_type to illuminate",
        ],
        "student_assessment_scores.pct_proficient": [
            "comparable across sources",
            "never multiply it by count_assigned",
        ],
        "student_assessment_scores.count_students": [
            "has timed out at standard grain",
            "count_taken",
            "report it as assessments taken, not students",
        ],
        "student_assessment_scores.count_assessments": [
            "not sittings",
            "Illuminate only",
            "thin base",
        ],
        "student_assessment_scores.avg_percent_correct": [
            "Illuminate only; null for every other source",
        ],
        "student_assessment_scores._count_scale_score": [
            "every source except Illuminate",
        ],
        "student_assessment_scores.pct_proficient_formative": [
            "about a third of module-coded Illuminate scores",
            'Not "all internal checkpoints"',
        ],
        # Assessments cube
        "student_assessments.assessment_type": [
            "computer-adaptive",
            "select a source",
            "college (SAT, ACT and PSAT, Official and Practice)",
            "carry no scores on this view today",
        ],
        "student_assessments.is_internal_assessment": [
            "Illuminate (KIPP-authored interims) only",
            "Filter assessment_type instead",
        ],
        "student_assessments.module_type": [
            "UA (Unit Assessment)",
            "not documented",
            "Do not expand TP, ET or WPP",
        ],
        "student_assessments.module_code": [
            "DIBELS: Composite",
            "Always pair it with academic_subject",
            "median date_taken",
        ],
        "student_assessments.academic_subject": [
            "Math and Reading",
            "Text Study",
            "open decision",
        ],
        "student_assessments.grade_level_tested": [
            "0 is kindergarten",
            "end-of-course",
            "filter grade_level instead",
        ],
        # Administrations and shared cubes
        "student_assessment_administrations.administration_period": [
            "Outside Round",
            "FL end-of-course and science: PM3",
            "use MOY",
            "never sort by date_taken",
            "Null for Illuminate and AP",
        ],
        "student_assessment_administrations.source_assessment_id": [
            "Illuminate only; null for every other source",
            "count_assessments",
        ],
        "locations.grade_band": [
            "a school attribute, not a student's grade",
            "A grade_band filter is a school filter",
        ],
        "courses.is_foundations": [
            "not a record of intervention services delivered",
        ],
        # The assessment view
        "student_assessment_scores_view": [
            "Enrollment-scoped",
            "group covers Illuminate, i-Ready and DIBELS",
            "There is no growth measure",
            "calibration difference",
            "which sitting counts is an open decision",
            "Repeat sittings inflate pct_proficient and count_scored",
            "release lag",
            "spiral review",
            "Resolve a name against staff_directory",
            "The only intervention signal on this view",
        ],
    }
)
