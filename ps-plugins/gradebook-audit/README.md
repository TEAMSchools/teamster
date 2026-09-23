# Gradebook Audit Plugin

A native PowerSchool plugin that manages gradebook assignment expectations and
audit reporting for KIPP NJ schools.

## Status

| Phase   | Description                          | Status         |
| ------- | ------------------------------------ | -------------- |
| Phase 1 | Expectations table + management page | ✅ Complete    |
| Phase 2 | Flags table + management page        | 🔲 Not started |
| Phase 3 | Exceptions table + management page   | 🔲 Not started |
| Phase 4 | Audit report — scaffold named query  | 🔲 Not started |
| Phase 5 | Audit report — actuals named query   | 🔲 Not started |
| Phase 6 | Teacher-facing report page           | 🔲 Not started |
| Phase 7 | Admin-facing summary page            | 🔲 Not started |

---

## Deployment Tracker

| Instance              | Region   | Version | Last Deployed | Table Created |
| --------------------- | -------- | ------- | ------------- | ------------- |
| psteam.kippnj.org     | Newark   | v2.5    | May 2026      | ✅            |
| camden.kippnj.org     | Camden   | v2.5    | May 2026      | ✅            |
| ps.kipppaterson.org   | Paterson | v2.5    | August 2026   | ✅            |
| kippnj2.clgpstest.com | Test     | v2.5    | May 2026      | ✅            |

---

## Prerequisites

Before installing or enabling the plugin on any PS instance, the
`U_EXPECTATIONS` table must be created manually via the PS Database Extensions
UI. See the full deployment guide:

📄 [`docs/deployment_guide.md`](./docs/deployment_guide.md)

> ⚠️ The plugin will throw a 500 error on enable if the table does not exist.

---

## File Inventory

```text
gradebook-audit/
├── plugin.xml
├── permissions_root/
│   └── gradebook_audit.permission_mappings.xml
├── queries_root/
│   └── gradebook_audit.named_queries.xml
├── WEB_ROOT/
│   └── admin/
│       └── gradebookaudit/
│           ├── gradebook_expectations.html        ← list page
│           ├── gradebook_expectations_edit.html   ← edit form
│           ├── gradebook_expectations_new.html    ← new record form
│           ├── gradebook_expectations_delete.html ← delete passthrough
│           └── gradebook_expectations_insert.html ← insert passthrough
└── docs/
    └── deployment_guide.md
```

> ⚠️ **The `gradebookaudit/` folder level is required — don't flatten it.**
> `plugin.xml` registers the left-nav link at `/admin/gradebookaudit/...`, and
> all four entries in `permission_mappings.xml` reference that same path. If the
> HTML files sit directly in `WEB_ROOT/admin/` instead, the nav link 404s and
> the permission mappings bind to nothing — **both fail silently**, with no
> error at install or enable time.
>
> This level was lost once already, during the migration out of the Claude
> Desktop project, and was restored after comparing against the zip deployed to
> Newark.

---

## Access Control

The list page guards itself with `~[if.not.memberof:Gradebook Group]` and
redirects everyone else to the PS admin home page.

The group is matched **by name**, not by ID — a group named exactly
`Gradebook Group` must exist on each instance. (Older docs said "Group #51";
that was just Newark's assigned ID and is irrelevant to access.)

To add a user: System Management → Security → Groups → Gradebook Group →
Members.

### 🛑 TODO — access control is not enforced

Two defects, found while deploying to Paterson in August 2026. Neither is fixed
yet.

**1. The guard is missing from four of five pages.** Only
`gradebook_expectations.html` carries `~[if.not.memberof:Gradebook Group]`. The
`_new`, `_edit`, `_insert`, and `_delete` pages have no check, so an
authenticated PS admin user who navigates directly to those URLs can add or
delete records without group membership. `_insert` and `_delete` are the ones
that write.

**2. The guard fails _open_ when the group does not exist.** Confirmed
empirically: `Gradebook Group` does not exist on `ps.kipppaterson.org`, and
`gradebook_expectations.html` loads there anyway. So on any instance without
that group, the existing check grants access rather than denying it — and
copying the same construct onto the other four pages would inherit the weakness.

**Current state:** on Paterson all five pages are reachable by any authenticated
PS admin user. Impact is limited while the table is empty; it rises as soon as
ops loads expectations data.

**The fix must fail closed.** Rather than "redirect if not a member", wrap page
content in a positive membership check so an absent or misspelled group denies
access instead of granting it. The PS-HTML construct for this is **not
documented in `docs/reference/`** — those PDFs don't cover `memberof` at all —
so the behavior has to be verified on `kippnj2.clgpstest.com` before it ships.

**Nothing is blocked.** The plugin works without `Gradebook Group` existing —
that's what failing open means. Creating and populating the group is a
nice-to-have, not a prerequisite for use.

### The actual decision

The repo is currently between two coherent positions, which is the real problem:

- **Gate by group.** Create and populate `Gradebook Group` per instance, wrap
  all five pages in a fail-closed membership check, bump to v2.6, deploy to all
  three regions. Access control then means something.
- **Don't gate.** Remove the vestigial guard from the list page and document
  that any PS admin who can reach the page can manage expectations, relying on
  PowerSchool's own page permissions. No setup, and the docs stop describing
  protection that isn't there.

Today the second is in force by accident while the docs describe the first.
Either end state is defensible; the gap between them is not.

> ⚠️ **If the fail-closed option is chosen, order matters.** A fail-closed guard
> deployed to an instance with no `Gradebook Group` locks out everyone,
> including admins — so the group must exist and be populated on that instance
> _before_ the fixed build reaches it. This is a constraint on that fix only,
> not on using the plugin.

Testing the fail-closed option needs a login that is **not** in the group.
Confirming that members still get in proves nothing, since that already works —
the negative case is the whole point.

---

## Key Technical Notes

> 📚 PowerSchool's own developer docs are PDFs in the Data Team's shared Drive
> folder, not files in this repo — the [index](../docs/reference/README.md)
> gives each one's Drive file ID. Doc 03 covers `plugin.xml`; doc 05 covers the
> PS-HTML page patterns these pages are built on.

- Plugin is hosted on CLG-managed PS instances — Oracle DDL auto-provisioning
  from `user_schema_root` XML does not work. Tables must be created manually.
- Extension group: `U_GRADEBOOK_AUDIT`
- Table name: `U_EXPECTATIONS`
- Named query: `com.kippnj.gradebookaudit.expectations_list`
- Left nav link registered via `admin.left_nav` ui_context in `plugin.xml`
- Mass delete uses a timed queue (1200ms per record) — no onload dependency
- CSV upload modal locks during upload to prevent accidental dismissal

---

## Updating the Plugin

1. Make changes in a branch
2. Bump the version in `plugin.xml`
3. PR → merge to `main`
4. Get the zip from the
   [Build plugin](https://github.com/TEAMSchools/teamster/actions/workflows/build-plugin.yaml)
   CI run (`plugin-zips` artifact), or run
   `uv run --no-project python ps-plugins/scripts/build_plugin.py` from the repo
   root — **don't zip by hand**
5. Upload via PS Plugin Configuration
6. Disable and re-enable the plugin
7. Update the deployment tracker above

> ⚠️ If the version number is not incremented, PS may show a warning — this can
> be safely ignored.

---

Maintained by the KTAF Data Team · data@kippnj.org
