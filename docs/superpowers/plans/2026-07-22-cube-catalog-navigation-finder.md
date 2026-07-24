# Cube Catalog Navigation and Field Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the generated Cube data catalog into domain-grouped
sections with a top "Views by domain" index and a filterable "Find a field"
finder, layered on the existing generator.

**Architecture:** Extend `scripts/generate_cube_reference.py` (parser +
renderer). The page stays a single generated Markdown file; a small vanilla-JS
enhancer plus a CSS file (wired via `mkdocs.yml` `extra_javascript` /
`extra_css`) turn the finder's Markdown table into an interactive, chip-styled
glossary at runtime. No inline HTML in the generated Markdown.

**Tech Stack:** Python 3.13 + `pyyaml` (generator), pytest (golden/unit tests),
MkDocs Material (`document$` observable), vanilla JS + CSS.

## Global Constraints

- **Run Python only via `uv run`** — never bare `python`.
- **Generated file stays pure Markdown** — no inline HTML (keeps prettier +
  `_normalize` freshness comparison and markdownlint working). Per-tag styling
  is applied at runtime by the JS enhancer.
- **Domains are folder-derived, never hardcoded** — a view's domain is the first
  path segment under `views_dir`; new `views/<domain>/` folders appear
  automatically. Friendly titles are a general transform (no lookup map) with
  `PII` kept uppercase.
- **Sensitivity is per member** — the `sensitive` flag is
  `exposed_name in SENSITIVE_MEMBERS`, never per-view.
- **Freshness unaffected** — all page changes are generator output; `--check`
  and the CI workflow keep working. JS/CSS/`mkdocs.yml` live outside the checked
  file.
- **Markdown rules** (CI-only): fenced blocks need a language (MD040); headings
  increment by one (MD001); `trunk check --force --no-fix <file> </dev/null`
  every edited `.md`.
- **Commit + push after every task** — this Codespace has reset and wiped
  uncommitted work mid-session; do not leave a task's work uncommitted.

## File Structure

| Path                                                                         | Responsibility                                                                                         |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `scripts/generate_cube_reference.py`                                         | domain capture, friendly titles, per-member sensitivity, restructured render, jump index, finder table |
| `tests/scripts/test_generate_cube_reference.py`                              | updated + new unit tests                                                                               |
| `tests/scripts/fixtures/cube_ref_sample/views/sample_domain/sample_view.yml` | fixture moved into a domain subfolder                                                                  |
| `docs/javascripts/cube-catalog.js`                                           | runtime finder enhancer (chips, filter, Measures, scroll)                                              |
| `docs/stylesheets/cube-catalog.css`                                          | finder + chip styles                                                                                   |
| `mkdocs.yml`                                                                 | `extra_javascript` + `extra_css` entries                                                               |
| `docs/reference/cube-data-catalog.md`                                        | GENERATED — regenerated                                                                                |

---

## Task 1: Parser — domain, friendly titles, per-member sensitivity

**Files:**

- Modify: `scripts/generate_cube_reference.py`
- Modify: `tests/scripts/test_generate_cube_reference.py`
- Move: `tests/scripts/fixtures/cube_ref_sample/views/sample_view.yml` →
  `.../views/sample_domain/sample_view.yml`

**Interfaces:**

- Produces: `friendly_name(slug: str) -> str`; `view_title(name: str) -> str`;
  `ResolvedView` gains `domain: str` (slug) and `domain_title`/`title` via
  helpers; `ResolvedMember` gains `sensitive: bool`.
  `resolve_view(view, cubes, domain="other")`.

- [ ] **Step 1: Move the fixture into a domain subfolder**

```bash
mkdir -p tests/scripts/fixtures/cube_ref_sample/views/sample_domain
git mv tests/scripts/fixtures/cube_ref_sample/views/sample_view.yml \
       tests/scripts/fixtures/cube_ref_sample/views/sample_domain/sample_view.yml
```

- [ ] **Step 2: Write failing tests**

Append to `tests/scripts/test_generate_cube_reference.py`:

```python
def test_friendly_name_titlecases_and_keeps_acronyms() -> None:
    assert gen.friendly_name("student_attendance") == "Student Attendance"
    assert gen.friendly_name("staff_pii") == "Staff PII"


def test_view_title_strips_view_suffix() -> None:
    assert gen.view_title("student_assessment_scores_view") == (
        "Student Assessment Scores"
    )
    assert gen.view_title("staff_directory") == "Staff Directory"


def test_parse_views_sets_domain_from_folder() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    view = next(
        v for v in gen.parse_views(FIXTURE_DIR / "views", cubes)
        if v.name == "sample_view"
    )
    assert view.domain == "sample_domain"


def test_resolve_view_flags_sensitive_members() -> None:
    # inline: a cube with a sensitive dim (personal_email) and a benign one
    cubes = {
        "c": {
            "personal_email": gen.CubeMember(
                name="personal_email", kind="dimension", type="string",
                description=None, primary_key=False, public=True,
            ),
            "grade_level": gen.CubeMember(
                name="grade_level", kind="dimension", type="number",
                description=None, primary_key=False, public=True,
            ),
        }
    }
    view = {"name": "v", "cubes": [{"join_path": "c",
            "includes": ["personal_email", "grade_level"]}]}
    members = {m.exposed_name: m for m in gen.resolve_view(view, cubes).members}
    assert members["personal_email"].sensitive is True
    assert members["grade_level"].sensitive is False
```

- [ ] **Step 3: Run to verify failure**

Run:
`uv run pytest tests/scripts/test_generate_cube_reference.py -k "friendly or view_title or domain or sensitive_members" -v`
Expected: FAIL (no `friendly_name`/`view_title`; `ResolvedView` has no `domain`;
`ResolvedMember` has no `sensitive`).

- [ ] **Step 4: Add friendly-title helpers**

Add near the top of `scripts/generate_cube_reference.py` (after the constants):

```python
_ACRONYMS = {"pii": "PII"}


def friendly_name(slug: str) -> str:
    """Human title from a snake_case slug; known acronyms stay uppercase."""
    return " ".join(
        _ACRONYMS.get(w.lower(), w.capitalize())
        for w in slug.replace("_", " ").split()
    )


def view_title(name: str) -> str:
    """Friendly view title; a trailing `_view` is dropped first."""
    base = name[:-5] if name.endswith("_view") else name
    return friendly_name(base)


def view_id(name: str) -> str:
    """Stable, collision-free heading id for a view (view names are unique)."""
    return "view-" + name.replace("_", "-")
```

`view_id` gives each view section an explicit anchor so links never collide with
same-named domain headings (e.g. a "Student Attendance" domain and view).

- [ ] **Step 5: Add `domain` to `ResolvedView`, `sensitive` to
      `ResolvedMember`**

In the `ResolvedMember` dataclass add `sensitive: bool`. In `ResolvedView` add
`domain: str`. Add convenience properties to `ResolvedView`:

```python
    @property
    def title(self) -> str:
        return view_title(self.name)

    @property
    def domain_title(self) -> str:
        return friendly_name(self.domain)
```

- [ ] **Step 6: Set `sensitive` in `resolve_view`; thread `domain`**

Change `resolve_view` signature to
`def resolve_view(view, cubes, domain: str = "other") -> ResolvedView:`. When
building each `ResolvedMember`, add
`sensitive=exposed_name in SENSITIVE_MEMBERS`. Set `domain=domain` on the
returned `ResolvedView`. In `parse_views`, compute the domain per file:

```python
    for path in sorted(views_dir.rglob("*.yml")):
        rel = path.relative_to(views_dir)
        domain = rel.parts[0] if len(rel.parts) > 1 else "other"
        doc = _load_yaml(path)
        for view in doc.get("views", []):
            views.append(resolve_view(view, cubes, domain=domain))
```

- [ ] **Step 7: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS (existing render tests still pass — render unchanged so far; the moved
fixture is still found by `rglob`).

- [ ] **Step 8: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py tests/scripts/fixtures/cube_ref_sample/views
git commit -m "feat(cube-docs): parser domain, friendly titles, per-member sensitivity

Refs #4438"
```

---

## Task 2: Restructure render into domain sections

**Files:**

- Modify: `scripts/generate_cube_reference.py` (`render_view`, `render_page`)
- Modify: `tests/scripts/test_generate_cube_reference.py`

**Interfaces:**

- Consumes: `ResolvedView.title`, `.domain`, `.domain_title` (Task 1).
- Produces: `render_view` emits an H3 view block (H4 sections, H5 folders);
  `render_page` groups views under H2 domain headings.

- [ ] **Step 1: Update the render tests**

Replace `test_render_page_has_banner_and_one_h2_per_view` and
`test_render_view_tables_and_placeholder` with:

```python
def test_render_page_groups_views_under_domain_h2() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    views = gen.parse_views(FIXTURE_DIR / "views", cubes)
    page = gen.render_page(views)

    assert page.startswith("# Cube data catalog\n")
    assert gen.BANNER in page
    # one H2 per domain (plus the two fixed sections), one H3 per view
    assert "## Sample Domain" in page
    assert "### Sample View" in page
    assert "## Views by domain" in page
    assert "## Find a field" in page


def test_render_view_block_has_code_name_and_tables() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    view = next(
        v for v in gen.parse_views(FIXTURE_DIR / "views", cubes)
        if v.name == "sample_view"
    )
    block = gen.render_view(view)

    assert block.startswith("### Sample View {#view-sample-view}")
    assert "`sample_view`" in block  # exact query name shown as code
    assert "#### Access" in block
    assert "#### Measures" in block
    assert "#### Dimensions" in block
    assert "##### Sample" in block  # folder now H5
    assert "| `no_desc_dim` | string | _No description._ |" in block
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -k render -v`
Expected: FAIL (headings still H2/H3/H4).

- [ ] **Step 3: Rewrite `render_view` to an H3 block**

Replace `render_view` so every heading drops one level and the code name is
shown:

```python
def render_view(view: ResolvedView) -> str:
    parts = [f"### {view.title} {{#{view_id(view.name)}}}", "", f"`{view.name}`", ""]
    if view.description:
        parts += [_cell(view.description), ""]
    parts += ["#### Access", "", _access_block(view.access), ""]

    measures = [m for m in view.members if m.kind == "measure"]
    if measures:
        parts += ["#### Measures", "", _member_table(measures), ""]

    dims = [m for m in view.members if m.kind == "dimension"]
    if dims:
        parts += ["#### Dimensions", ""]
        for folder in _folder_order(view):
            in_folder = [m for m in dims if m.folder == folder]
            parts += [f"##### {folder}", "", _member_table(in_folder), ""]
    return "\n".join(parts).rstrip()
```

- [ ] **Step 4: Rewrite `render_page` to group by domain**

```python
def render_page(views: list[ResolvedView]) -> str:
    by_domain: dict[str, list[ResolvedView]] = {}
    for v in sorted(views, key=lambda v: v.name):
        by_domain.setdefault(v.domain, []).append(v)

    sections: list[str] = ["# Cube data catalog", BANNER, INTRO]
    sections.append(render_domain_index(by_domain))
    sections.append(render_finder(views))
    for domain in sorted(by_domain):
        sections.append(f"## {friendly_name(domain)}")
        for v in by_domain[domain]:
            sections.append(render_view(v))
    return "\n\n".join(sections) + "\n"
```

Note: `render_domain_index` and `render_finder` are added in Tasks 3 and 4. To
keep this task's tests green in isolation, add temporary stubs now and replace
them next:

```python
def render_domain_index(by_domain: dict[str, list[ResolvedView]]) -> str:
    return "## Views by domain"


def render_finder(views: list[ResolvedView]) -> str:
    return "## Find a field"
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py
git commit -m "feat(cube-docs): group catalog views under domain sections

Refs #4438"
```

---

## Task 3: "Views by domain" jump index

**Files:**

- Modify: `scripts/generate_cube_reference.py` (`render_domain_index`)
- Modify: `tests/scripts/test_generate_cube_reference.py`

**Interfaces:**

- Produces: `render_domain_index(by_domain) -> str` — an H2 section with an H3
  per domain and a bulleted view list (friendly title linked to the view anchor,
  exact name in code, one-line summary).

- [ ] **Step 1: Write the failing test**

```python
def test_domain_index_lists_views_with_links() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    views = gen.parse_views(FIXTURE_DIR / "views", cubes)
    by_domain = {"sample_domain": views}
    idx = gen.render_domain_index(by_domain)

    assert idx.startswith("## Views by domain")
    assert "### Sample Domain" in idx
    assert "[Sample View](#view-sample-view)" in idx
    assert "`sample_view`" in idx
```

- [ ] **Step 2: Run to verify failure**

Run:
`uv run pytest tests/scripts/test_generate_cube_reference.py -k domain_index -v`
Expected: FAIL (stub returns only the heading).

- [ ] **Step 3: Implement `render_domain_index`**

Replace the Task 2 stub. `_anchor` slugifies a title the way Material does
(lowercase, non-alphanumerics to hyphens, collapse repeats, strip ends):

```python
def _summary(view: ResolvedView) -> str:
    if not view.description:
        return ""
    first = re.split(r"(?<=[.])\s", view.description.strip(), maxsplit=1)[0]
    return _cell(first)


def render_domain_index(by_domain: dict[str, list[ResolvedView]]) -> str:
    parts = ["## Views by domain", ""]
    for domain in sorted(by_domain):
        parts.append(f"### {friendly_name(domain)}")
        parts.append("")
        for v in sorted(by_domain[domain], key=lambda v: v.name):
            summary = _summary(v)
            tail = f" — {summary}" if summary else ""
            parts.append(f"- [{v.title}](#{view_id(v.name)}) (`{v.name}`){tail}")
        parts.append("")
    return "\n".join(parts).rstrip()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py
git commit -m "feat(cube-docs): add Views-by-domain jump index

Refs #4438"
```

---

## Task 4: "Find a field" Markdown finder table

**Files:**

- Modify: `scripts/generate_cube_reference.py` (`render_finder`)
- Modify: `tests/scripts/test_generate_cube_reference.py`

**Interfaces:**

- Produces: `render_finder(views) -> str` — an H2 section with a two-column
  Markdown table (`| Field | Details |`). The Details cell holds the view link,
  the tags as backtick code spans (`domain`, `kind`, `type`, and `sensitive`
  when applicable), then the description. Rows are ordered domain-then-field.
  The JS enhancer (Task 5) restyles the code spans into chips.

- [ ] **Step 1: Write the failing tests**

```python
def test_finder_table_row_shape_and_sensitive() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    views = gen.parse_views(FIXTURE_DIR / "views", cubes)
    finder = gen.render_finder(views)

    assert finder.startswith("## Find a field")
    assert "| Field | Details |" in finder
    # a benign member: view link + tags, no `sensitive` span
    assert "`grade_level`" in finder
    assert "[Sample View](#view-sample-view)" in finder
    assert "`dimension`" in finder
    # no member in the fixture is sensitive
    assert "`sensitive`" not in finder


def test_finder_row_includes_sensitive_span_when_flagged() -> None:
    cubes = {
        "c": {
            "personal_email": gen.CubeMember(
                name="personal_email", kind="dimension", type="string",
                description="Personal email.", primary_key=False, public=True,
            ),
        }
    }
    view = gen.resolve_view(
        {"name": "staff_pii", "cubes": [{"join_path": "c",
         "includes": ["personal_email"]}]},
        cubes, domain="staff",
    )
    finder = gen.render_finder([view])
    # the sensitive tag rides in the row for a flagged member
    assert "`personal_email`" in finder
    assert "`sensitive`" in finder
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -k finder -v`
Expected: FAIL (stub returns only the heading).

- [ ] **Step 3: Implement `render_finder`**

Replace the Task 2 stub:

```python
FINDER_INTRO = (
    "One row per field across every view. Filtering matches the field name, "
    "its tags, and the description; each row links to a domain section with the "
    "full per-view field lists. (Tags render as chips once the page's script "
    "loads.)"
)


def _finder_rows(views: list[ResolvedView]) -> list[str]:
    rows: list[tuple[str, str, ResolvedView, ResolvedMember]] = []
    for v in views:
        for m in v.members:
            rows.append((v.domain, m.exposed_name, v, m))
    rows.sort(key=lambda r: (r[0], r[1]))

    lines: list[str] = []
    for _domain, _name, v, m in rows:
        tags = [f"`{v.domain}`", f"`{m.kind}`"]
        if m.type:
            tags.append(f"`{_cell(m.type)}`")
        if m.sensitive:
            tags.append("`sensitive`")
        link = f"[{v.title}](#{view_id(v.name)})"
        desc = _cell(m.description) if m.description else PLACEHOLDER
        details = f"{link} {' '.join(tags)} — {desc}"
        lines.append(f"| `{m.exposed_name}` | {details} |")
    return lines


def render_finder(views: list[ResolvedView]) -> str:
    parts = ["## Find a field", "", FINDER_INTRO, ""]
    parts.append("| Field | Details |")
    parts.append("| --- | --- |")
    parts += _finder_rows(views)
    return "\n".join(parts).rstrip()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py
git commit -m "feat(cube-docs): add Find-a-field markdown finder table

Refs #4438"
```

---

## Task 5: JS enhancer + CSS + MkDocs wiring

**Files:**

- Create: `docs/javascripts/cube-catalog.js`
- Create: `docs/stylesheets/cube-catalog.css`
- Modify: `mkdocs.yml`

**Interfaces:** none (runtime only; not unit-tested).

- [ ] **Step 1: Write the CSS**

Create `docs/stylesheets/cube-catalog.css`:

```css
/* Find-a-field finder: chips + filter + capped scroll */
.cube-finder-controls {
  display: flex;
  gap: 0.8rem;
  align-items: center;
  flex-wrap: wrap;
  margin: 0.6rem 0;
}
.cube-finder-controls input[type="search"] {
  flex: 1;
  min-width: 240px;
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--md-default-fg-color--lighter);
  border-radius: 4px;
  font: inherit;
}
.cube-finder-measures {
  border: 1px solid var(--md-default-fg-color--lighter);
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  font: inherit;
  cursor: pointer;
  background: transparent;
  color: var(--md-primary-fg-color);
}
.cube-finder-measures[aria-pressed="true"] {
  background: var(--md-primary-fg-color);
  color: var(--md-primary-bg-color);
}
.cube-finder-scroll {
  max-height: 34rem;
  overflow: auto;
}
.cube-finder-scroll table {
  width: 100%;
}
.cube-finder-scroll thead th {
  position: sticky;
  top: 0;
  background: var(--md-default-bg-color);
  z-index: 1;
}
.cube-chip {
  display: inline-block;
  font-size: 0.72rem;
  padding: 0.05rem 0.45rem;
  border-radius: 10px;
  white-space: nowrap;
  background: color-mix(in srgb, var(--md-primary-fg-color) 14%, transparent);
  color: var(--md-primary-fg-color);
}
.cube-chip--sensitive {
  background: color-mix(in srgb, #c65a20 16%, transparent);
  color: #c65a20;
}
```

- [ ] **Step 2: Write the JS enhancer**

Create `docs/javascripts/cube-catalog.js`:

```javascript
// Enhance the generated "Find a field" table: chips, filter, Measures toggle,
// capped scroll. Runs on Material's document$ so it survives instant-nav.
(function () {
  const KINDS = new Set(["measure", "dimension"]);
  const TYPES = new Set([
    "string",
    "number",
    "time",
    "boolean",
    "count",
    "count_distinct",
  ]);

  function classify(text) {
    if (text === "sensitive") return "cube-chip cube-chip--sensitive";
    return "cube-chip"; // domain / kind / type all share the calm chip
  }

  function enhance() {
    const heading = document.getElementById("find-a-field");
    if (!heading) return;
    let table = heading.nextElementSibling;
    while (table && table.tagName !== "TABLE") table = table.nextElementSibling;
    if (!table || table.dataset.cubeEnhanced) return;
    table.dataset.cubeEnhanced = "1";

    // Restyle the backtick code spans in the Details column into chips.
    table.querySelectorAll("tbody tr td:nth-child(2) code").forEach((code) => {
      const span = document.createElement("span");
      span.className = classify(code.textContent);
      span.textContent = code.textContent;
      code.replaceWith(span);
    });

    // Controls: filter box + Measures toggle.
    const controls = document.createElement("div");
    controls.className = "cube-finder-controls";
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Filter fields, tags, or description keywords…";
    const measures = document.createElement("button");
    measures.type = "button";
    measures.className = "cube-finder-measures";
    measures.textContent = "Measures";
    measures.setAttribute("aria-pressed", "false");
    controls.append(input, measures);

    const scroll = document.createElement("div");
    scroll.className = "cube-finder-scroll";
    table.replaceWith(scroll);
    scroll.append(table);
    scroll.parentNode.insertBefore(controls, scroll);

    const rows = Array.from(table.querySelectorAll("tbody tr"));
    let measuresOnly = false;

    function apply() {
      const q = input.value.trim().toLowerCase();
      rows.forEach((row) => {
        const text = row.textContent.toLowerCase();
        const isMeasure = /\bmeasure\b/.test(text);
        const hit = (!q || text.includes(q)) && (!measuresOnly || isMeasure);
        row.hidden = !hit;
      });
    }
    input.addEventListener("input", apply);
    measures.addEventListener("click", () => {
      measuresOnly = !measuresOnly;
      measures.setAttribute("aria-pressed", measuresOnly ? "true" : "false");
      apply();
    });
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(enhance);
  } else {
    document.addEventListener("DOMContentLoaded", enhance);
  }
})();
```

- [ ] **Step 3: Wire MkDocs**

In `mkdocs.yml`, after the `markdown_extensions:` block (top level), add:

```yaml
extra_css:
  - stylesheets/cube-catalog.css

extra_javascript:
  - javascripts/cube-catalog.js
```

- [ ] **Step 4: Lint the JS/CSS/YAML**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/javascripts/cube-catalog.js docs/stylesheets/cube-catalog.css mkdocs.yml </dev/null`
Expected: no issues (fix any prettier/eslint findings and re-run).

- [ ] **Step 5: Commit**

```bash
git add docs/javascripts/cube-catalog.js docs/stylesheets/cube-catalog.css mkdocs.yml
git commit -m "feat(cube-docs): finder JS enhancer + chip styles

Refs #4438"
```

---

## Task 6: Regenerate, verify freshness, build, document

**Files:**

- Modify (generated): `docs/reference/cube-data-catalog.md`
- Modify: `docs/CLAUDE.md`, `scripts/CLAUDE.md` (note the JS/CSS assets)

**Interfaces:** none.

- [ ] **Step 1: Regenerate the catalog**

Run: `uv run scripts/generate_cube_reference.py` Expected:
`wrote 6 view sections ...` (or current count).

- [ ] **Step 2: Sanity-check structure**

Run: `grep -c '^## ' docs/reference/cube-data-catalog.md` Expected: domains + 2
(Views by domain, Find a field).

Run: `grep -c '^### ' docs/reference/cube-data-catalog.md` Expected: one per
view (plus per-domain H3s in the index — confirm the count is
`views + domains`).

- [ ] **Step 3: Freshness check (padding-tolerant)**

Run: `uv run scripts/generate_cube_reference.py --check && echo CLEAN` Expected:
`CLEAN` after the pre-commit `fmt` pads the committed file (commit first if
needed, then re-run — table padding is neutralized by `_normalize`).

- [ ] **Step 4: Build the site**

Run: `uv run --group docs mkdocs build 2>&1 | tail -5` Expected: build succeeds;
no new warnings referencing the catalog page.

- [ ] **Step 5: Lint the generated page**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/reference/cube-data-catalog.md </dev/null`
Expected: only prettier table-padding (applied at commit); no markdownlint
issues (no MD033 — the finder is pure Markdown).

- [ ] **Step 6: Update the docs notes**

In `scripts/CLAUDE.md`, extend the `generate_cube_reference.py` catalog note to
mention the finder relies on `docs/javascripts/cube-catalog.js` +
`docs/stylesheets/cube-catalog.css` (wired in `mkdocs.yml`), which are NOT part
of the freshness check. In `docs/CLAUDE.md`, note the same under the generated
`cube-data-catalog.md` entry.

- [ ] **Step 7: Commit**

```bash
git add docs/reference/cube-data-catalog.md docs/CLAUDE.md scripts/CLAUDE.md
git commit -m "docs(cube): regenerate catalog with nav + finder; document assets

Refs #4438"
```

- [ ] **Step 8: Push and confirm CI**

```bash
git push
```

Then confirm on the PR: Trunk, the freshness `check`, and dbt Cloud are green.
Drive the built page (or the deployed preview) to confirm the finder filters,
the Measures toggle limits to measures, chips render, and the table scrolls.

---

## Final verification

- [ ] `uv run pytest tests/scripts/test_generate_cube_reference.py -v` — all
      pass.
- [ ] `uv run scripts/generate_cube_reference.py --check && echo CLEAN` — CLEAN.
- [ ] `uv run --group docs mkdocs build` — succeeds.
- [ ] Manual drive of the finder on the built site (filter, Measures, chips,
      scroll, view links jump to the right section).
