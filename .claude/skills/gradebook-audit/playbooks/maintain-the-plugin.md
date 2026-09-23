# Procedure: Build, version, and deploy the PowerSchool plugin

**Trigger phrases:** "we need to change the gradebook audit plugin", "add a
field/page to the gradebook audit PS plugin", "build the plugin zip", "deploy
the plugin to Newark/Camden/Paterson/test", "the plugin isn't showing up in
PowerSchool", "bump the plugin version"

**Source lives in this repo, at
[`ps-plugins/gradebook-audit/`](../../../../ps-plugins/gradebook-audit/).** It
is not a separate checkout and not a Claude Desktop project — edit it like any
other file in `teamster`, on a branch, same as everything else in this repo.

For the PowerSchool-specific gotchas (CLG hosting, no server-level DDL, the
three-region-plus-test deployment model, PS-HTML/`trunk fmt` interaction, doc
reading order), read [`ps-plugins/CLAUDE.md`](../../../../ps-plugins/CLAUDE.md)
rather than expecting them repeated here. That file is the authority; this
procedure only covers the parts specific to the gradebook-audit plugin and to
closing the loop with the dbt model and the end-user skill.

## The steps

1. **Make the change** under `ps-plugins/gradebook-audit/`. If the change
   touches `WEB_ROOT/admin/gradebookaudit/*.html`, keep in mind two things this
   skill also owns (see `references/published-sheets.md` and
   `ship-a-skill-update.md` below):
   - a page-behavior change is exactly the kind of thing the end-user skill's
     `powerschool-navigation.md` walkthrough describes to Teaching & Learning
     screen by screen, so plan on updating it too;
   - CI enforces this: a PR that changes a `WEB_ROOT` page without also touching
     `ps-plugins/skills/**` fails the `build-plugin` workflow, unless the PR
     title carries `[skill-unaffected]`. Don't reach for that tag just to
     unblock the build — use it only when you've actually confirmed the
     walkthrough still matches the screens.
2. **Bump `version` in `plugin.xml`** — every change, no exceptions. PowerSchool
   warns (harmlessly) if you forget, but the deployment tracker below depends on
   the version actually changing.
3. **Build with the script, never by hand:**

   ```bash
   uv run --no-project python ps-plugins/scripts/build_plugin.py
   ```

   `--no-project` because the script is standard-library-only and does not need
   (and should not resolve against) the main `teamster` project's dependencies.
   It writes `ps-plugins/dist/gradebook_audit_v<version>.zip`. Hand-zipping is
   exactly how the `WEB_ROOT/admin/gradebookaudit/` folder level went missing
   once before — the script validates that every path referenced in the plugin's
   XML resolves to a real packaged file, and now also checks two contracts that
   used to drift silently:
   - the columns the named queries declare on `U_EXPECTATIONS` against the
     columns the **dlt** `stg_powerschool__u_expectations`
     (`src/dbt/powerschool/models/sis/staging/dlt/`) actually projects. That is
     the only one of the three variants the check can use: `odbc/` is archived
     and disabled by default, and the kipptaf-level model is a `union_relations`
     wrapper that enumerates no columns.
   - the plugin's CSV import header against what the end-user skill's
     `references/csv-format.md` documents.

   If the header check fails, there is a third place to check that the script
   does not know about: the `PS Plugin CSV Template` tab in the Gradebook Audit
   Template sheet's Reports copy is the literal header row people copy from, and
   nothing keeps it in sync automatically — see
   `references/published-sheets.md`.

   A CI run does the same build (`.github/workflows/build-plugin.yaml`) and
   additionally runs `tests/ps_plugins`, so a local build failure will fail the
   PR too — fix it before pushing rather than after.

4. **The `gradebookaudit/` folder level is load-bearing — don't flatten it.**
   `plugin.xml` registers the nav link at
   `/admin/gradebookaudit/gradebook_expectations.html`, and every entry in
   `permission_mappings.xml` references that same path. Move the HTML files up a
   level and the nav link 404s and the permissions bind to nothing — **both fail
   silently**, with no error at install or enable time.
5. **The `U_EXPECTATIONS` table must already exist on the target instance before
   the plugin is enabled, or it 500s.** PowerSchool is CLG-hosted, so there is
   no server-level access to run the DDL yourself — the table is created by hand
   through System Management → Data → Database Extensions. The full walkthrough
   is
   [`ps-plugins/gradebook-audit/docs/deployment_guide.md`](../../../../ps-plugins/gradebook-audit/docs/deployment_guide.md).
6. **Deploy to each instance individually — Newark, Camden, Paterson, and the
   shared test instance.** Uploading to one does not touch the others. Upload
   via System Management → Server → Plugin Configuration, then disable and
   re-enable the plugin.
7. **Update the deployment tracker after every deploy** — the table in
   [`ps-plugins/gradebook-audit/README.md`](../../../../ps-plugins/gradebook-audit/README.md#deployment-tracker),
   not the top-level `ps-plugins/README.md`. Record the new version and the
   deploy date per instance; a tracker that says v2.5 while an instance is
   actually running v2.6 is exactly the kind of drift this skill exists to
   prevent.

## Reference PDFs are not in this repo

PowerSchool's vendor developer docs (plugin XML schema, database extensions,
PS-HTML page patterns, PowerTeacher Pro) live in the shared Data Team Drive
folder, not in git — indexed with file IDs, reading order, and what each one
covers at
[`ps-plugins/docs/reference/README.md`](../../../../ps-plugins/docs/reference/README.md).
Start there before changing `plugin.xml`, a `U_` table, a named query, or any
PS-HTML page.
