# Guides Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `docs/getting-started.md` into `docs/guides/index.md` (Account
Setup + routing) and `docs/guides/local-development.md` (Local Development
content), fix the missing sidenav on the Guides section, and update all
cross-references.

**Architecture:** `getting-started.md` is deleted and replaced by two files: a
section index (`guides/index.md`) and a new guide
(`guides/local-development.md`). MkDocs Material's `navigation.indexes` feature
is enabled so the Guides section header becomes a clickable link to
`guides/index.md`. All internal links pointing to `getting-started.md` are
updated.

**Tech Stack:** MkDocs, Material for MkDocs, Markdown

---

## File Map

| Action | Path                               | Responsibility                                     |
| ------ | ---------------------------------- | -------------------------------------------------- |
| Create | `docs/guides/index.md`             | Account Setup prose + routing table to all guides  |
| Create | `docs/guides/local-development.md` | Extracted Local Development content                |
| Delete | `docs/getting-started.md`          | Replaced by the two files above                    |
| Modify | `mkdocs.yml`                       | Enable `navigation.indexes`; update `nav:`         |
| Modify | `docs/README.md`                   | Update `getting-started.md` link → `guides/`       |
| Modify | `docs/troubleshooting/vscode.md`   | Update `../getting-started.md` link → `../guides/` |
| Modify | `docs/CLAUDE.md`                   | Update structure map                               |

---

### Task 1: Establish baseline

- [ ] **Step 1: Verify the build currently passes**

  ```bash
  uv run mkdocs build --strict 2>&1 | tail -5
  ```

  Expected: `INFO - Documentation built in ...` with no warnings or errors. If
  it fails, stop and investigate before proceeding.

- [ ] **Step 2: Commit baseline note (optional)**

  Only needed if the build is already dirty. Otherwise skip.

---

### Task 2: Create `docs/guides/local-development.md`

**Files:**

- Create: `docs/guides/local-development.md`

- [ ] **Step 1: Create the file**

  Content is extracted verbatim from the Local Development section of
  `docs/getting-started.md` (lines 52–105). Create
  `docs/guides/local-development.md` with:

  ````markdown
  # Local Development

  ## Prerequisites

  Install [uv](https://docs.astral.sh/uv/) for Python package management.

  ## Setup

  ```bash
  # Install dependencies
  uv sync --frozen

  # Run Dagster webserver locally
  uv run dagster dev

  # Validate definitions for a code location
  uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions
  ```
  ````

  ## dbt

  Before running dbt assets locally, prepare and package the dbt project:

  ```bash
  uv run dagster-dbt project prepare-and-package \
    --file src/teamster/code_locations/kipptaf/__init__.py
  ```

  ## Linting and formatting

  [Trunk](https://trunk.io/) runs all linters:

  ```bash
  trunk check   # lint
  trunk fmt     # format
  ```

  | Language | Linter(s)                                                                                   |
  | -------- | ------------------------------------------------------------------------------------------- |
  | SQL      | [SQLFluff](https://docs.sqlfluff.com/en/stable/rules.html), [sqlfmt](https://sqlfmt.com/)   |
  | Python   | [Ruff](https://docs.astral.sh/ruff/rules/), [Pyright](https://github.com/microsoft/pyright) |

  ## Testing

  ```bash
  # Run all tests
  uv run pytest

  # Run a single test file
  uv run pytest tests/test_dagster_definitions.py

  # Run asset-specific tests (require env vars / external connections)
  uv run pytest tests/assets/test_assets_dbt.py
  ```

  Note: The triple-backtick fences above are illustrative — write the actual
  fenced code blocks properly in the file (the outer wrapper here is just
  quoting). The file has no frontmatter.

- [ ] **Step 2: Verify the file exists**

  ```bash
  head -3 docs/guides/local-development.md
  ```

  Expected: `# Local Development`

---

### Task 3: Create `docs/guides/index.md`

**Files:**

- Create: `docs/guides/index.md`

- [ ] **Step 1: Create the file**

  Content is Account Setup from `docs/getting-started.md` (lines 8–47) plus a
  routing table. No frontmatter (no `hide: navigation`).

  ```markdown
  # Guides

  ## Account Setup

  ### GitHub

  To contribute, you must be a member of our
  [Data Team](https://github.com/orgs/TEAMSchools/teams/data-team). Your ability
  to approve and merge pull requests depends on your subgroup:

  - [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers)
  - [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)
  - [Admins](https://github.com/orgs/TEAMSchools/teams/admins)

  ### Google Workspace

  To access our BigQuery project and its datasets, you must be a member of the
  **TEAMster Analysts KTAF** Google security group.

  ### dbt Cloud

  #### Development dataset

  dbt Cloud creates a personal development dataset in BigQuery for each user,
  named using your username as a prefix. Please prefix yours with an underscore
  (`_`) — BigQuery hides datasets starting with `_` from the left nav, keeping
  the project list readable.

  Set this in **Account settings → Credentials → Development credentials**.

  #### sqlfmt

  <!-- adapted from https://docs.getdbt.com/docs/cloud/dbt-cloud-ide/lint-format#format-sql -->

  We use [sqlfmt](https://sqlfmt.com/) for SQL formatting. To enable it in dbt
  Cloud:

  1. Open a `.sql` file on a development branch.
  2. Click the **Code Quality** tab in the console, then **`</> Config`**.
  3. Select the `sqlfmt` radio button.
  4. Click **Format** to auto-format the file.

  ## Guides

  | Guide                                     | Description                                                            |
  | ----------------------------------------- | ---------------------------------------------------------------------- |
  | [Codespaces](codespaces.md)               | Setting up and using GitHub Codespaces                                 |
  | [Local Development](local-development.md) | Installing dependencies, running Dagster locally, linting, and testing |
  | [Dagster](dagster.md)                     | Tableau scheduling, backfills, branch deployments, monitoring runs     |
  | [Google Sheets & Forms](google-sheets.md) | Adding and updating Google Sheets and Forms sources                    |
  ```

- [ ] **Step 2: Verify the file exists and has no frontmatter**

  ```bash
  head -5 docs/guides/index.md
  ```

  Expected: first line is `# Guides` with no `---` frontmatter block above it.

---

### Task 4: Update `mkdocs.yml`

**Files:**

- Modify: `mkdocs.yml`

- [ ] **Step 1: Enable `navigation.indexes` feature**

  In `mkdocs.yml`, add `navigation.indexes` to the `theme.features` list. The
  list currently ends at `toc.follow`. Add it after `navigation.tabs.sticky`:

  Before:

  ```yaml
  features:
    - content.action.edit
    - content.code.copy
    - navigation.instant
    - navigation.sections
    - navigation.tabs
    - navigation.tabs.sticky
    - navigation.top
    - search.highlight
    - search.suggest
    - toc.follow
  ```

  After:

  ```yaml
  features:
    - content.action.edit
    - content.code.copy
    - navigation.instant
    - navigation.indexes
    - navigation.sections
    - navigation.tabs
    - navigation.tabs.sticky
    - navigation.top
    - search.highlight
    - search.suggest
    - toc.follow
  ```

- [ ] **Step 2: Update the `nav:` Guides section**

  Before:

  ```yaml
  - Guides:
      - Getting Started: getting-started.md
      - Codespaces: guides/codespaces.md
      - Dagster: guides/dagster.md
      - Google Sheets & Forms: guides/google-sheets.md
  ```

  After:

  ```yaml
  - Guides:
      - guides/index.md
      - Codespaces: guides/codespaces.md
      - Local Development: guides/local-development.md
      - Dagster: guides/dagster.md
      - Google Sheets & Forms: guides/google-sheets.md
  ```

  The `guides/index.md` entry has no title key — this is the Material convention
  for a section index page. The Guides tab in the top nav will link to
  `guides/index.md`.

- [ ] **Step 3: Verify the YAML is valid**

  ```bash
  uv run python -c "import yaml; yaml.safe_load(open('mkdocs.yml'))" && echo "OK"
  ```

  Expected: `OK`

---

### Task 5: Fix cross-references

**Files:**

- Modify: `docs/README.md`
- Modify: `docs/troubleshooting/vscode.md`

- [ ] **Step 1: Update `docs/README.md`**

  Line 62 currently reads:

  ```markdown
  1. [Getting Started](getting-started.md) — account setup, Codespaces, local
     dev
  ```

  Replace with:

  ```markdown
  1. [Guides](guides/) — account setup and task-focused walkthroughs
  ```

- [ ] **Step 2: Update `docs/troubleshooting/vscode.md`**

  Line 77 currently reads:

  ```markdown
  **See also:** [Getting Started](../getting-started.md) ·
  ```

  Replace with:

  ```markdown
  **See also:** [Guides](../guides/) ·
  ```

---

### Task 6: Delete `docs/getting-started.md`

**Files:**

- Delete: `docs/getting-started.md`

- [ ] **Step 1: Delete the file**

  ```bash
  git rm docs/getting-started.md
  ```

- [ ] **Step 2: Verify it is gone**

  ```bash
  ls docs/getting-started.md 2>&1
  ```

  Expected:
  `ls: cannot access 'docs/getting-started.md': No such file or directory`

---

### Task 7: Update `docs/CLAUDE.md`

**Files:**

- Modify: `docs/CLAUDE.md`

- [ ] **Step 1: Update the structure map**

  In the `## Structure` section, replace:

  ```text
  getting-started.md       # Onboarding guide
  ```

  with the guides directory entries. The guides section currently lists:

  ```text
  guides/                  # Task-focused walkthroughs
    dagster.md
    google-sheets.md
  ```

  Replace with:

  ```text
  guides/                  # Task-focused walkthroughs
    index.md               # Account setup + guide routing table (section landing)
    codespaces.md
    local-development.md
    dagster.md
    google-sheets.md
  ```

  Also remove `getting-started.md` from the root-level file listing.

---

### Task 8: Verify and commit

- [ ] **Step 1: Run the full build with strict mode**

  ```bash
  uv run mkdocs build --strict 2>&1 | tail -10
  ```

  Expected: `INFO - Documentation built in ...` with no warnings or errors. Any
  `WARNING` about unresolved links is a failure — investigate and fix before
  committing.

- [ ] **Step 2: Commit all changes**

  ```bash
  git add docs/guides/index.md \
          docs/guides/local-development.md \
          docs/README.md \
          docs/troubleshooting/vscode.md \
          docs/CLAUDE.md \
          mkdocs.yml
  git commit -m "refactor(docs): split getting-started into guides index and local-development guide

  - Replace getting-started.md with guides/index.md (section landing)
  - Extract local dev content to guides/local-development.md
  - Enable navigation.indexes for clickable Guides section header
  - Fix hide:navigation bug that was suppressing the sidenav
  - Update all cross-references"
  ```
