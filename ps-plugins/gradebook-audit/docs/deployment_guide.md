# KIPP NJ Gradebook Audit Plugin

## Deployment Guide — Phase 1: Expectations Table

---

## Before You Begin

Work through the parts in order. Part 1 must be complete before Part 2, or
enabling the plugin throws a 500 error.

> 🛑 **Part 2 must be done with the school selector set to `District`.**
> Installing the plugin from an individual school's context is not supported.
> Creating the table in Part 1 is unaffected — the selector only matters for the
> install itself, so if you built the table from a school context you don't need
> to redo it. Just switch to `District` before Part 2.

> ℹ️ The plugin resource report (see _Verify the Install_) shows whatever school
> context the _viewer_ currently has in its header — so a school name appearing
> there is not evidence of a school-level install. Don't use that header to
> judge where the plugin lives.

---

## Part 1: Create the U_EXPECTATIONS Table Manually

The plugin cannot auto-create database tables on CLG-hosted PS instances due to
Oracle DDL privilege restrictions. The `U_EXPECTATIONS` table must be created
manually via the Database Extensions UI on each PS instance before enabling the
plugin.

> ⚠️ Complete this entire section before installing or enabling the plugin. If
> the table does not exist when the plugin is enabled, PS will throw a 500
> error.

### Step-by-Step

1. Log in to the PS admin console.
2. Navigate to **System Management → Data → Database Extensions**.
3. In Step 1 (Choose Functional Area), set the left dropdown to **Other**. After
   a brief lag, the **Add Independent Table** button will appear on the right.
   Click it.

   > ⚠️ There may be a short lag after selecting Other before the Add
   > Independent Table button appears. Wait for it — do not refresh.

4. In Step 2 (Choose or Add New Database Extension Group), click **Add** (top
   right). An **Add Extension** modal will appear with `U_` pre-filled. Type
   `GRADEBOOK_AUDIT` after the prefix and click **Apply**. PS will also
   auto-create a `U_IndependentTable_Extension` placeholder row — delete it
   using the minus (−) button.

5. Select **U_GRADEBOOK_AUDIT** (radio button) and click **Next**.

6. In Step 3 (Choose or Add New Database Extension Table), PS will auto-create a
   `U_DEF_INDEPENDENT` placeholder. Click the pencil (✏️) button on that row.
   Set the table name to `EXPECTATIONS` (PS will prefix it to `U_EXPECTATIONS`)
   and enter the description:

   > _The list of expected assignment counts for the current academic year, week
   > by week._

   Click Apply.

7. Select **U_EXPECTATIONS** (radio button) and click **Next**.

8. In Step 4 (Create New Fields), click **Add** and enter each field below one
   at a time. Do **not** add an ID field — PS creates it automatically.

   > ℹ️ **Previously blocked on Paterson, now resolved.** The **Add Field**
   > modal on `ps.kipppaterson.org` would not accept keyboard input, which
   > blocked table creation there for months. Confirmed working as of
   > August 2026. Recorded here because if it recurs on any instance, it's a
   > CLG-side PS bug — not a mistake in these steps and not a fault in the
   > plugin. If it does recur, stop: don't enable the plugin against a table
   > with missing fields.

   | Field Name     | Data Type   | Default Value | Description                                                              |
   | -------------- | ----------- | ------------- | ------------------------------------------------------------------------ |
   | `school_level` | String(2)   | ES            | The school level: ES, MS or HS                                           |
   | `quarter`      | String(2)   |               | The quarter/term for the current academic year (Q1 to Q4)                |
   | `week_number`  | Integer     |               | The week number for the given quarter. Numbering restarts every quarter. |
   | `cnt_w`        | Integer     | 0             | The number of Work Habit assignments expected YTD.                       |
   | `cnt_h`        | Integer     | 0             | The number of Homework assignments expected YTD.                         |
   | `cnt_f`        | Integer     | 0             | The number of Formative assignments expected YTD.                        |
   | `cnt_s`        | Integer     | 0             | The number of Summative assignments expected YTD.                        |
   | `notes`        | String(255) |               | Notes for teachers.                                                      |

   > ℹ️ **Field names are lowercase snake_case**, matching the convention used
   > throughout the KTAF database — and matching what is already deployed on the
   > other instances. **Group and table names are the exception:** they stay
   > uppercase with the `U_` prefix (`U_GRADEBOOK_AUDIT`, `U_EXPECTATIONS`),
   > which is why Step 6 above has you type `EXPECTATIONS` rather than
   > `expectations`.

   > ⚠️ PS displays fields alphabetically in the UI — this is normal and does
   > not affect functionality.

9. Click **Submit** to save the table and all fields.

10. _(Optional)_ If you have access to Oracle APEX, verify the table was created
    by running:
    ```sql
    SELECT table_name FROM all_tables WHERE table_name LIKE '%EXPECT%'
    ```
    Expected result: a row returning `U_EXPECTATIONS`. Skip this step if you do
    not have APEX access.

### Editing the Table After Creation

To view or add fields to an existing table, follow the same navigation flow:

- System Management → Data → Database Extensions
- Step 1: Select Other → wait → click Add Independent Table
- Step 2: PS will auto-create a `U_IndependentTable_Extension` placeholder —
  delete it. Select `U_GRADEBOOK_AUDIT` → Next
- Step 3: Select `U_EXPECTATIONS` → Next
- Step 4: Existing fields are shown. Click Add to add new fields.

> ⚠️ PS does not allow editing or deleting fields that contain data. To modify a
> field definition, you must first delete all records via the Gradebook
> Expectations plugin page, make the field changes, then re-import data via CSV.

---

## Part 2: Install and Enable the Plugin

> ⚠️ Do not attempt to install or enable the plugin until Part 1 is complete and
> `U_EXPECTATIONS` is confirmed to exist in Oracle.

### Step-by-Step

1. Obtain the latest plugin zip. **Don't build it by hand** — hand-zipping once
   dropped a required folder level and produced a plugin that installed cleanly
   and then silently didn't work. Either:
   - **Download from CI:** repo → **Actions** → **Build plugin** → latest run →
     download the `plugin-zips` artifact, or
   - **Build locally:** `python3 scripts/build_plugin.py`, which writes to
     `dist/` and fails if any path in the plugin's XML doesn't resolve.
2. Log in to the PS admin console.
3. Navigate to **System Management → Server → Plugin Configuration**.
4. Click **Install** — the button is labelled just `Install`, not "Install
   Plugin". Choose the zip file, then click **Install** again on the
   confirmation screen.
5. Once installed, locate **KIPP NJ Gradebook Audit** in the plugin list and
   click **Enable**.
6. Verify the plugin is active — the **Gradebook Expectations** link should
   appear in the left navigation bar under Applications.

> ⚠️ If the plugin throws a 500 error on enable, confirm `U_EXPECTATIONS` exists
> in Oracle (Part 1, Step 10) before proceeding.

### Verify the Install

PS exposes everything it parsed out of the plugin package on one screen. This is
the fastest way to confirm an install landed correctly, and it needs no group
access — so it can be done before Part 3.

**To reach it:** System Management → Server → **Plugin Configuration** → click
the plugin **name** (`KIPP NJ Gradebook Audit`), not the checkbox.

Compare against these expected values, taken from the known-good Newark install:

| Section              | Field            | Expected                                                                                                                                                                   |
| -------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| General Information  | Plugin Name      | `KIPP NJ Gradebook Audit`                                                                                                                                                  |
|                      | Plugin Version   | matches the `version` in `plugin.xml` (2.5 as of this writing)                                                                                                             |
|                      | Publisher        | `KTAF Data Team`                                                                                                                                                           |
|                      | Publisher Email  | `data@kippnj.org`                                                                                                                                                          |
|                      | Enabled          | `True`                                                                                                                                                                     |
| PowerQueries         | Query            | `com.kippnj.gradebookaudit.expectations_list`                                                                                                                              |
|                      | Core Table       | `u_expectations`                                                                                                                                                           |
|                      | Flattened        | `True`                                                                                                                                                                     |
|                      | Returned Columns | 9 rows: `id`, `school_level`, `quarter`, `week_number`, `cnt_w`, `cnt_h`, `cnt_f`, `cnt_s`, `notes` — each named `u_expectations.<field>` with the bare field as its alias |
| Web Resources        | Resource         | **5** files, every one under `WEB_ROOT/admin/gradebookaudit/`, each `text/html`                                                                                            |
| Permission Resources | Name             | `gradebook_audit.permission_mappings.xml`, containing 4 `<permission>` entries                                                                                             |

> ✅ **The single most valuable line here is the Web Resources paths.** If they
> read `WEB_ROOT/admin/gradebook_expectations.html` — without the
> `gradebookaudit/` segment — the zip was built wrong and the plugin will
> install cleanly and then silently not work. Rebuild with
> `scripts/build_plugin.py` and reinstall.

> ⚠️ **What this screen does _not_ prove.** Returned Columns are read from the
> named query's XML, not from Oracle, so a perfect report is still consistent
> with a missing `U_EXPECTATIONS` table or mismatched field names. Only loading
> the page (Part 4) exercises the database. Treat this as "the package is
> correct", not "the install works".

**Best practice:** print this screen to PDF on each install and diff it against
a known-good instance. Only two fields should legitimately differ:

- the **school context** in the page header (reflects the viewer, not the
  install)
- **Installed/Updated On**

Anything else differing is a real discrepancy worth chasing. This method
verified the Paterson install in August 2026 against Newark's: identical on
every substantive field.

### Updating the Plugin

To update an existing plugin installation with a new version:

1. Navigate to **System Management → Server → Plugin Configuration**.
2. Find **KIPP NJ Gradebook Audit** and click **Update Plugin**.
3. Upload the new zip file.
4. Disable and re-enable the plugin to pick up any changes to `plugin.xml`.

> ⚠️ Do not delete and reinstall unless necessary — updating in place preserves
> the table and all data.

> ℹ️ If the plugin version number in `plugin.xml` is not incremented before
> uploading, PS may show a warning. This warning can be safely ignored — the
> update will still apply correctly.

---

## Part 3: Grant Access to Users

Access is controlled by PS group membership. The list page guards itself with
`~[if.not.memberof:Gradebook Group]` and redirects everyone else to the PS admin
home page.

> ⚠️ **The group is matched by name, not by ID.** Earlier versions of this guide
> said "Group #51" — that is simply the ID Newark happened to assign, and it has
> no bearing on access. What matters is that a group named exactly
> `Gradebook Group` exists, with that spelling and capitalization. On a new
> instance, create it; don't try to force a particular ID.

> 🛑 **Known gap:** only the list page carries this guard.
> `gradebook_expectations_new.html`, `_edit`, `_insert`, and `_delete` have no
> group check, so any authenticated PS admin user who navigates directly to
> those URLs can add or delete expectations records without being in
> `Gradebook Group`. Requires an admin login, so this is not public exposure —
> but the access control is not as broad as it looks. Fix pending.

### To find, create, or populate the group

1. Navigate to **System Management → Security → Groups**.
2. Search for **Gradebook Group**.
   - **Exists** → open it.
   - **Doesn't exist** → create it with the name exactly `Gradebook Group`.
3. Go to the **Members** tab.
4. Add the appropriate user(s).

---

## Part 4: Load Expectations Data

Once the plugin is enabled and the user has access, expectations data can be
loaded via CSV upload on the Gradebook Expectations page.

### Accessing the Page

| Instance        | URL                                                                            |
| --------------- | ------------------------------------------------------------------------------ |
| Test            | https://kippnj2.clgpstest.com/admin/gradebookaudit/gradebook_expectations.html |
| Newark (prod)   | https://psteam.kippnj.org/admin/gradebookaudit/gradebook_expectations.html     |
| Camden (prod)   | https://camden.kippnj.org/admin/gradebookaudit/gradebook_expectations.html     |
| Paterson (prod) | https://ps.kipppaterson.org/admin/gradebookaudit/gradebook_expectations.html   |

> ℹ️ The `gradebookaudit/` segment in these URLs is not optional — it's the
> folder level `plugin.xml` and the permission mappings both expect. If a page
> 404s at one of these URLs on an instance where the plugin is enabled, the
> installed zip is missing that folder. Rebuild it with
> `scripts/build_plugin.py` rather than zipping by hand.

Or use the **Gradebook Expectations** link in the left navigation bar under
Applications.

### CSV Upload

- Click **Upload CSV** and follow the on-screen instructions.
- Use **Add** mode to append records to existing data.
- Use **Replace** mode to clear all existing records and replace with the
  uploaded file.
- Do not close the modal during upload — the page will reload automatically when
  done.

> ⚠️ Great things take time. Do not exit the window during upload.

### CSV Template Format

Download the template from the Upload CSV modal — it is the safest starting
point.

The header row is **required and validated positionally**. It must be exactly:

```text
School Level,Quarter,Week Number,W,H,F,S,Notes
```

> 🛑 **These are not the database column names.** The underlying fields are
> `school_level`, `week_number`, `cnt_w`, `cnt_h`, `cnt_f`, `cnt_s` — but the
> CSV header uses the display names above. A file headed `school_level,...` or
> `cnt_W,...` is **rejected outright** with a "Header row does not match
> template" alert, and nothing imports. Earlier versions of this guide listed
> the database names here, which is why hand-built files were being refused.

Header matching is case-insensitive and trims whitespace, so `school level`
works; the _order_ is what cannot vary.

| Column       | Rules                                                                 |
| ------------ | --------------------------------------------------------------------- |
| School Level | Must be `ES`, `MS`, or `HS`. Lowercase input is accepted and upcased. |
| Quarter      | Must be `Q1`–`Q4`. Lowercase accepted.                                |
| Week Number  | Any integer. Restarts each quarter.                                   |
| W            | Work Habits — integer, **required, cannot be blank**                  |
| H            | Homework — integer, required                                          |
| F            | Formative Mastery — integer, required                                 |
| S            | Summative Mastery — integer, required                                 |
| Notes        | Optional free text. Commas allowed if the value is quoted.            |

**How bad data behaves — read this before trusting a successful import:**

- A row failing any rule above is **skipped, not fatal.** The import continues
  with the remaining rows, so a file with 20 bad rows reports success and
  silently loads fewer records than you supplied. Check the preview's row counts
  before importing.
- **Duplicates are keyed on `School Level` + `Quarter` + `Week Number`.** In
  **Add** mode a duplicate creates a genuine second record — the preview warns
  in yellow but does not block it. Use **Replace** if you are reloading a period
  you have already loaded.
- **Replace deletes every existing record** across all school levels and
  quarters before inserting, not just the rows in your file. There is a
  confirmation prompt.
- Rows insert one at a time, so large files take a while. This is expected.

---

## Part 5: Hand Off to the Data Platform

Installing the plugin does **not** get the data into BigQuery. The
`U_EXPECTATIONS` table has to be added to that instance's ingestion config in
the data platform repo
([`TEAMSchools/teamster`](https://github.com/TEAMSchools/teamster)) before
anything downstream can read it. Until that happens the plugin works fine in PS
and the data is invisible to every dashboard and model.

**The change is one file per instance:**

```text
src/teamster/code_locations/<code_location>/powerschool/sis/dlt/config/assets.yaml
```

Add, in alphabetical position among the other `table_name` entries:

```yaml
- table_name: u_expectations
  cursor_column: whenmodified
  intraday: true
  nightly: false
```

Code locations map to regions as `kippnewark`, `kippcamden`, `kipppaterson`.

**No dbt changes are needed.** `stg_powerschool__u_expectations.sql` and the
`powerschool_dlt` source entry are templated on `{{ project_name }}`, so they
apply to every code location already.

Raise this as an issue on `teamster` and assign it to the data platform owner
(Charlie, as of 2026). Newark and Camden were done together in one pass, so if
multiple instances are being deployed, batch them.

> ⚠️ The ingestion cursor is `whenmodified`, one of the audit columns PS adds to
> database extension tables automatically. It isn't in the plugin's named query,
> so it's easy to forget it exists — but incremental loading depends on it.

---

## PS Instance Reference

| Instance            | Region   | URL                   |
| ------------------- | -------- | --------------------- |
| Test Server         | —        | kippnj2.clgpstest.com |
| Newark Production   | Newark   | psteam.kippnj.org     |
| Camden Production   | Camden   | camden.kippnj.org     |
| Paterson Production | Paterson | ps.kipppaterson.org   |

---

_KTAF Data Team · data@kippnj.org · Last updated August 2026_
