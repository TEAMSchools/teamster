# PowerSchool Reference Documentation

Vendor documentation for building PS plugins. **The documents are PDFs in the
Data Team's shared Drive folder. None of them are in this repo** — this file is
the index: what each one covers, when to reach for it, and the Drive file ID to
fetch it by.

They were previously held in a Claude Desktop project, which meant only one
person could see them. Indexing them here means anyone working on a plugin in
this repo — or any AI assistant session working in it — reaches the same
reference material.

> **Internal use only.** These are PowerSchool Group LLC / Pearson copyrighted
> documents, kept for KTAF staff working on our own plugins. Do not redistribute
> outside the network.

---

## Start here

New to PS plugin development, read in this order: **02** for what a plugin
actually is, then **03** for the `plugin.xml` schema, then **04** and **05** for
database extensions.

| Drive file ID                       | Document                           |
| ----------------------------------- | ---------------------------------- |
| `1LH0b5PSX_49PKnPOz3I2W_kD2QDI50Gd` | 2 - PS Plugins Intro               |
| `1jRvB4-Cc9N8kQ1zDOGb_bDNtOtDwrRl1` | 3 - PS Plugins XML                 |
| `1N8uHTD9oJhZpQAEa0UsYR2oy1yF6qC5r` | 4 - Database Extensions            |
| `18P1l28IanSON-lPuMCwR560HWKzxQujE` | 5 - Advanced User Guide            |
| `1ZxRjgezkF1Mi2ZTAyE6Q0WCwamq69mq5` | 6 - PowerTeacher Pro Customization |
| `1wtd7lmAB9LEI0yPtIQ6tTEdDjTJlt7TY` | 1 - PS Data Dictionary             |

### Document descriptions

**2 - PS Plugins Intro** (2 pages)  
What a plugin is; `plugin.xml` as a single file vs. a packaged zip; installing
via System > System Settings > Plugin Management Dashboard. Reach for it when
orienting for the first time, or explaining the deployment model to someone new.

**3 - PS Plugins XML** (12 pages)  
Full `plugin.xml` element hierarchy — `<links>`, `<link>`, `<ui_contexts>`,
`<ui_context>`, `<permissions>`, `<publisher>`, `<oauth>`, `<saml>`, `<openid>`,
`<registration>`. Notes which PS version each element arrived in (21.11.0
through 25.2.0). **The one you'll open most.** Reach for it when making any
change to `plugin.xml` — nav links, `ui_context` ids, permissions, version
attributes.

**4 - Database Extensions** (2 pages)  
Database extensions from the admin side: one-to-one, one-to-many, and
independent tables, and how they combine. Current — captured from the live admin
docs, © 2026. Reach for it when creating or altering a `U_` table through the
Database Extensions UI.

**5 - Advanced User Guide** (44 pages)  
The deep one: page customization against database extensions, PS-HTML form
elements, `tlist_child`, one-to-one and one-to-many code samples. Reach for it
when writing or debugging the HTML pages — form field naming, list rendering,
insert/update patterns.

**6 - PowerTeacher Pro Customization** (15 pages)  
PowerTeacher Pro customization: plugin folder layout under
`web_root/teachers/powerteacher-pro`, student custom pages, message-key i18n
properties, top-level `<div>` configuration attributes. Reach for it during
Phase 6 — the teacher-facing report page. PTP customization works differently
from admin pages.

**1 - PS Data Dictionary**  
Every PS table and field: names, types, sizes. Reach for it when looking up a
core table or field before writing a named query. The largest of the six by far
— see [Why they live in Drive](#why-they-live-in-drive).

### Version caveat on 05

Document 05 is **version 1.4, released June 2015, written against PS release
9.x** (originally a Pearson-era document owned by K-12 Sales). It is still the
most complete treatment of PS-HTML and `tlist_child` anywhere, which is why it's
in the set — but it long predates our instances. Where 05 and 04 disagree, **04
wins**. Treat 05's specifics as a strong hint to verify on the test instance
(`kippnj2.clgpstest.com`), not as settled fact.

Documents 02, 03, and 04 were captured from PowerSchool's live documentation
sites in April 2026, so they reflect roughly current behavior. They are
snapshots, not living documents — if something doesn't match what a PS instance
actually does, the instance is right and the snapshot is stale.

### Why they live in Drive

They are PowerSchool's PDFs, not ours, and a git repo is a poor home for them:
each re-capture stores another copy in history, permanently, in a repo whose
actual plugin code is under 100 KB. Document 01 makes the case on its own — the
PS Data Dictionary is 18.8 MB and is regenerated for every PowerSchool release,
so committing it would mean a fresh ~19 MB blob on every PS upgrade. It is also
a lookup table rather than a guide: you search it for one field and close it.

So all six stay in the Data Team shared Drive folder, which everyone on the team
can already reach:

- **Folder:**
  https://drive.google.com/drive/folders/1qjtKWlEE2XrfUXBh4QAodEX2g6c8do4T
- **01, PS Data Dictionary:**
  https://drive.google.com/file/d/1wtd7lmAB9LEI0yPtIQ6tTEdDjTJlt7TY/view

Every document's Drive file ID is in the table above, so an assistant session
with a Drive connector can fetch one directly without searching.

---

## Reading one

The folder is shared with the Codespaces service account
(`codespaces@teamster-332318.iam.gserviceaccount.com`), so a script under
`uv run` downloads the bytes to disk with Application Default Credentials. That
is the working path.

The Google Drive connector returns file content as base64, which
`check-output.sh` redacts as a high-entropy string, so binary files cannot be
read through the connector. Use it for metadata only.

---

## Source URLs

For re-capturing these when PowerSchool updates them:

- 02, 03 — `support.powerschool.com/developer/#/page/plugins` and
  `.../#/page/plugin-xml`
- 04 — `ps.powerschool-docs.com/pssis-admin/latest/database-extensions`
- 05 — PowerSchool article 74828 (Database Extension and Page Customization
  Developer Guide)

---

Maintained by the KTAF Data Team · data@kippnj.org
