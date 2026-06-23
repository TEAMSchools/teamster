# Staff PII Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict six personal/sensitive staff fields in the `staff_detail`
Cube view to a new `cube-access-staff-pii` group, mirroring the existing student
two-tier access pattern.

**Architecture:** Add a second `access_policy` block to the `staff_detail` view:
the base `cube-access-staff-data` block keeps `includes: "*"` but adds an
`excludes:` list for the six fields; a new `cube-access-staff-pii` block grants
`includes: "*"`. Re-comment the backing `staff` cube dimensions to reflect the
real tiers, and update the cube CLAUDE.md note. No `cube.js` change — group
membership resolves dynamically.

**Tech Stack:** Cube semantic layer (YAML data models), BigQuery driver, Cube
Cloud. Lint via trunk (yamllint). Spec:
[docs/superpowers/specs/2026-06-22-staff-pii-gate-design.md](2026-06-22-staff-pii-gate-design.md),
issue [#4236](https://github.com/TEAMSchools/teamster/issues/4236).

## Global Constraints

- **No automated test harness exists for Cube access policies.** Per-task
  verification is `trunk check` (YAML lint) + a manual Cube Cloud Dev Mode
  validation at the end (Task 4). Do not invent a pytest cycle.
- **One cube/view per file; filename matches `name:`.** Do not rename files.
- **Never use the Cube Playground Models tab** — it overwrites hand-authored
  YAML.
- **Gated fields (exact set, do not add or remove):** `personal_email`,
  `personal_cell_phone`, `birth_date`, `gender_identity`, `race`, `is_hispanic`.
- **Not gated (stay in base tier):** `full_name`, `first_name`, `last_name`,
  `staff_unique_id`, `work_email`, `google_email`, `active_directory_username`,
  all `staff_manager_*`, `original_hire_date`, `rehire_date`, `staff_key`.
- **trunk runs at commit (fmt) and pre-push (check).** Run
  `/workspaces/teamster/.trunk/tools/trunk check --force <file>` from the repo
  root (cwd `/workspaces/teamster`) before declaring a file clean.
- **Working branch:** `cristinabaldor/feat/claude-staff-pii-gate` (already
  checked out; not a worktree). All edits target files under
  `/workspaces/teamster/`.

---

### Task 1: Add the PII sub-tier to `staff_detail`

**Files:**

- Modify: `src/cube/model/views/staff/staff_detail.yml` (the `access_policy:`
  block, currently the last block in the file)

**Interfaces:**

- Consumes: nothing.
- Produces: the `cube-access-staff-pii` group name, referenced by the docs in
  Task 3.

- [ ] **Step 1: Replace the `access_policy` block**

Find the current block (single `cube-access-staff-data` group with
`includes: "*"`) and replace the entire `access_policy:` section with:

```yaml
access_policy:
  # Non-PII staff tier: roster/employment structure without personal or
  # sensitive data. Personal contact, DOB, and demographics are gated to
  # cube-access-staff-pii. Work-directory info (names, work/google email,
  # AD username, manager contacts) stays visible — already internally public.
  - group: cube-access-staff-data
    member_level:
      includes: "*"
      excludes:
        - personal_email
        - personal_cell_phone
        - birth_date
        - gender_identity
        - race
        - is_hispanic
  - group: cube-access-staff-pii
    member_level:
      includes: "*"
```

- [ ] **Step 2: Lint the file**

Run:
`cd /workspaces/teamster && .trunk/tools/trunk check --force src/cube/model/views/staff/staff_detail.yml`
Expected: `✔ No issues`

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/staff/staff_detail.yml
git commit -m "feat(cube): gate personal staff fields behind cube-access-staff-pii

Refs #4236"
```

---

### Task 2: Re-comment the `staff` cube dimensions

**Files:**

- Modify: `src/cube/model/cubes/staff/staff.yml` (dimension comment lines)

**Interfaces:**

- Consumes: nothing.
- Produces: nothing (comments only — no member names change).

The current comments are inconsistent: demographics are uncommented; directory
identifiers are mislabeled `# PII —`. There are several identical
`# PII — name.` and `# PII — contact.` lines — disambiguate each edit by the
dimension `- name:` immediately below the comment.

- [ ] **Step 1: Update gated-field comments**

For `birth_date` (currently `# PII — date of birth.`):

```yaml
# Gated to cube-access-staff-pii — date of birth.
- name: birth_date
```

For `personal_email` (currently `# PII — contact.` directly above
`- name: personal_email`):

```yaml
# Gated to cube-access-staff-pii — personal contact.
- name: personal_email
```

For `personal_cell_phone` (currently `# PII — contact.` directly above
`- name: personal_cell_phone`):

```yaml
# Gated to cube-access-staff-pii — personal contact.
- name: personal_cell_phone
```

- [ ] **Step 2: Add comments to the demographic dimensions**

`gender_identity`, `race`, and `is_hispanic` currently have **no** comment line.
Add this line immediately above each `- name:`:

```yaml
# Demographic — gated to cube-access-staff-pii in staff_detail; aggregate-only breakdown in staff_summary.
```

So, for example:

```yaml
# Demographic — gated to cube-access-staff-pii in staff_detail; aggregate-only breakdown in staff_summary.
- name: gender_identity
```

Repeat verbatim above `- name: race` and `- name: is_hispanic`.

- [ ] **Step 3: Update directory-identifier comments**

These five dimensions stay in the base tier. Replace each one's comment
(`# PII — employee identifier.` / `# PII — name.` / `# PII — contact.` /
`# PII — credential/identifier.`) with the same line, disambiguating by the
`- name:` below:

```yaml
# Staff-directory identifier — visible to all cube-access-staff-data (internally public).
```

Apply above: `- name: staff_unique_id`, `- name: full_name`,
`- name: first_name`, `- name: last_name`, `- name: work_email`,
`- name: google_email`, `- name: active_directory_username`.

- [ ] **Step 4: Lint the file**

Run:
`cd /workspaces/teamster && .trunk/tools/trunk check --force src/cube/model/cubes/staff/staff.yml`
Expected: `✔ No issues`

- [ ] **Step 5: Sanity-check the comment count**

Run: `grep -c "cube-access-staff" src/cube/model/cubes/staff/staff.yml`
Expected: `13` — one per re-commented dimension: 3 gated contact/DOB
(`personal_email`, `personal_cell_phone`, `birth_date`) + 3 demographic
(`gender_identity`, `race`, `is_hispanic`) + 7 directory (`staff_unique_id`,
`full_name`, `first_name`, `last_name`, `work_email`, `google_email`,
`active_directory_username`).

- [ ] **Step 6: Commit**

```bash
git add src/cube/model/cubes/staff/staff.yml
git commit -m "docs(cube): re-comment staff dimensions to reflect PII tiers

Refs #4236"
```

---

### Task 3: Update the cube CLAUDE.md "Staff views" note

**Files:**

- Modify: `src/cube/CLAUDE.md` (the "Staff views" bullet under "## View access
  policies")

**Interfaces:**

- Consumes: the `cube-access-staff-pii` group name from Task 1.
- Produces: nothing.

- [ ] **Step 1: Replace the "Staff views" bullet**

Find the bullet that begins `- **Staff views** use a single` and ends with
`see-staff-but-not-PII need arises.` Replace the whole bullet with:

```markdown
- **Staff views**: `staff_summary` uses a single `cube-access-staff-data` block
  with `includes: "*"` — aggregate demographics only, no direct identifiers.
  `staff_detail` uses two blocks: `cube-access-staff-data` with `includes: "*"`
  and `excludes:` the personal/sensitive fields (`personal_email`,
  `personal_cell_phone`, `birth_date`, `gender_identity`, `race`,
  `is_hispanic`), plus `cube-access-staff-pii` with `includes: "*"`.
  Work-directory info (names, work/google email, AD username, `staff_unique_id`,
  manager contacts) stays in the base tier — internally public. Demographics are
  gated row-level in `staff_detail` but remain valid aggregate breakdowns in
  `staff_summary` (low-n suppression is tracked separately, #4237).
```

- [ ] **Step 2: Lint the file**

Run:
`cd /workspaces/teamster && .trunk/tools/trunk check --force src/cube/CLAUDE.md`
Expected: `✔ No issues`

- [ ] **Step 3: Commit**

```bash
git add src/cube/CLAUDE.md
git commit -m "docs(cube): document staff_detail two-tier access policy

Refs #4236"
```

---

### Task 4: Validate in Cube Cloud Dev Mode (manual)

**Files:** none.

**Interfaces:**

- Consumes: the deployed branch.

This task is **manual and requires the user** — Claude cannot run the long-lived
Cube dev server, and branch staging envs are not auto-created from pushes.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin cristinabaldor/feat/claude-staff-pii-gate
```

- [ ] **Step 2: Spin up the branch staging env**

In Cube Cloud → Data Model → Dev Mode → add the branch
`cristinabaldor/feat/claude-staff-pii-gate` by name. Confirm
`GOOGLE_DIRECTORY_SA_KEY` / `GOOGLE_DIRECTORY_SA_SUBJECT` are set on that
environment (branch staging does not fully inherit production secrets).

- [ ] **Step 3: Verify the model compiles**

Compile a `staff_detail` query via `/sql`. Expected: it compiles (this confirms
the YAML is structurally valid and the view is present). `/sql` compiles even
against hidden members, so this is a presence/syntax check, not an enforcement
check.

- [ ] **Step 4: Verify enforcement with `/load`**

Using a test account in `cube-access-staff-data` but NOT in
`cube-access-staff-pii`, run a `/load` query selecting `personal_email` (or any
of the six gated fields). Expected: a 500 "You requested hidden member" /
`rlsAccessDenied` — the field is hidden. With a `cube-access-staff-pii` account,
the same query succeeds. (`/load` enforces hiding; `/sql` does not.)

- [ ] **Step 5: Confirm `staff_summary` is unaffected**

Run a `staff_summary` query grouping by `race` for a
`cube-access-staff-data`-only account. Expected: succeeds (demographics remain
aggregate breakdowns there).

---

## Post-implementation

- Open the PR using `.github/pull_request_template.md`; body references
  `Closes #4236`.
- **Rollout prerequisite (admin, outside repo):** the `cube-access-staff-pii`
  Workspace group must be created and members enrolled before/with merge. On
  merge, any `cube-access-staff-data` user not also in the new group loses the
  six fields. Coordinate before merging.
