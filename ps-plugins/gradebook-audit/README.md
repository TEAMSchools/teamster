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

Access is managed through PS group membership. The group is matched **by name**,
not by ID — a group named exactly `Gradebook Group` must exist on each instance.
(Older docs said "Group #51"; that was just Newark's assigned ID and is
irrelevant to access.)

To add a user: System Management → Security → Groups → Gradebook Group →
Members.

### 🛑 Known security defects

The plugin has known security defects. They are tracked privately with the Data
Team, not in this public repository. Before changing any page that adds, edits,
or deletes expectations, ask the Data Team for the details.

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
