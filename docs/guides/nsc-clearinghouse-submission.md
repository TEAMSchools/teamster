# NSC Clearinghouse Submission

This guide walks through producing and uploading a **StudentTracker
Non-Consent Request** file to the National Student Clearinghouse (NSC). KIPP
submits this file three times per year (November, March, and June) to receive
updated postsecondary enrollment data for alumni.

## Who does this

A member of the KIPP Forward / data team pulls the file and uploads it. No
coding is required — the data is prepared automatically by the data pipeline.

---

## Submission schedule

| Submission | When to upload | Enrollment data returned |
| ---------- | -------------- | ------------------------ |
| Fall       | Early November | Fall semester enrollments |
| Spring     | Early March    | Spring semester enrollments |
| Graduation | Early June     | Degree completions |

The pipeline automatically selects the correct alumni cohorts and search begin
date for each submission window.

---

## Step 1 — Find the Google Sheet

The submission data lives in BigQuery as
`kipptaf_google_sheets.rpt_gsheets__nsc_clearinghouse_submission`. If your team
has a connected Google Sheet that refreshes from this table, open it. Otherwise,
ask the data team to export it for you.

The sheet contains one row per record:

| Column | Contents |
| ------ | -------- |
| `row_order` | Sort key: 1 = header, 2 = student rows, 3 = trailer |
| `field_1`–`field_12` | The 12 tab-delimited columns required by NSC |

---

## Step 2 — Sort and clean the sheet

1. **Sort** the entire sheet by `row_order` ascending (1 → 2 → 3).
   The header row (H1) must be first, student rows (D1) in the middle, and
   the trailer row (T1) last.
2. **Hide or delete** the `row_order` column — it must not appear in the
   uploaded file.
3. **Do not add, remove, or reorder** any other columns. The NSC file format
   is positional: each column maps to a fixed field.

!!! warning "All columns must stay as text"
    Make sure Excel or Sheets has not auto-converted any column to a number or
    date format. Dates must appear as `YYYYMMDD` (e.g. `20250901`), and codes
    like `00` must keep their leading zero. If values look wrong, format the
    entire sheet as plain text before downloading.

---

## Step 3 — Download as tab-delimited text

In Google Sheets:

1. **File → Download → Tab Separated Values (.tsv)**
2. Rename the downloaded file. The filename **must** include the 6-digit entity
   code `601193` and must not contain special characters
   (`! @ # $ % ^ & * ( ) +`). Underscores are allowed.

   Example: `601193_kipp_nj_clearinghouse_20251101.txt`

3. Change the file extension from `.tsv` to `.txt` if needed — NSC expects
   `.txt`.

---

## Step 4 — Upload to NSC Secure FTP

1. Go to **[https://ftps.nslc.org/](https://ftps.nslc.org/)** and log in with
   the KIPP account credentials (stored in 1Password under *NSC StudentTracker
   SFTP*).
2. Upload the `.txt` file. Do **not** email the file — NSC does not accept
   submissions via email.
3. NSC will process the file and return enrollment data, typically within a few
   business days.

!!! note "No FTP account?"
    Contact `studenttracker@studentclearinghouse.org` to request access.

---

## Special case — Reconciliation / backfill run

If you need to submit a file that covers a longer historical period than the
standard window (for example, a one-time backfill spanning several years),
ask the data team to re-run the model with a custom start date:

```bash
dbt run --select rpt_gsheets__nsc_clearinghouse_submission \
  --vars '{"nsc_search_begin_date": "YYYY-MM-DD"}'
```

Replace `YYYY-MM-DD` with the earliest date you want NSC to search from
(e.g. `2020-09-01` to capture records going back to fall 2020).
