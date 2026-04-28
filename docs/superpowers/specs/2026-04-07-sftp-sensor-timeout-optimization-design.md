# SFTP Sensor Timeout Optimization

## Problem

Two kipptaf sensors hit the 300s sensor execution timeout:

- `kipptaf__adp__workforce_now__sftp_assets_sensor`
- `kipptaf__couchdrop__sftp_asset_job_sensor`

Both perform a full recursive directory listing every tick, then filter all
files against regex patterns for each asset. No incremental logic — the cursor
tracks per-asset timestamps but the directory scan is always exhaustive.

### ADP WFN SFTP sensor

**File:**
`src/teamster/code_locations/kipptaf/adp/workforce_now/sftp/sensors.py`

`ssh_adp_workforce_now.listdir_attr_r()` is called with no arguments —
recursively traverses the entire SFTP root via paramiko. Every file is then
checked against every asset's regex, even files older than the cursor. No
`exclude_dirs` passed despite the `./payroll` subtree being irrelevant.

### Couchdrop sensor

**File:** `src/teamster/libraries/couchdrop/sensors.py`

`google_drive.files_list_recursive()` recursively lists the entire Google Drive
folder tree. The query (`src/teamster/libraries/google/drive/resources.py:154`)
uses only `'{folder_id}' in parents and trashed = false` — no `modifiedTime`
filter. Every file in the tree is returned and filtered client-side.

## Design

### ADP WFN SFTP sensor

Four changes:

#### 1. Pass `exclude_dirs` to `listdir_attr_r()`

The sensor currently calls `listdir_attr_r()` with no arguments. Pass
`exclude_dirs=["./payroll"]` to skip the payroll subtree during the walk.

#### 2. Add `min_mtime` to `listdir_attr_r` / `_inner_listdir_attr_r`

New parameter `min_mtime: float | None = None`. When set, skip files with
`st_mtime <= min_mtime` during the recursive walk — never append them to the
result list. The sensor computes `min(cursor.values(), default=0)` across asset
cursor entries (excluding `__dir_mtimes`) and passes it in.

#### 3. Directory-level mtime caching

New parameter `dir_mtimes: dict[str, float] | None = None` on `listdir_attr_r` /
`_inner_listdir_attr_r`. Before recursing into a directory, compare the
directory's `st_mtime` against the cached value. If unchanged, skip the entire
subtree. When `dir_mtimes` is provided, `listdir_attr_r` returns
`tuple[list[tuple[SFTPAttributes, str]], dict[str, float]]` (files + updated
dir_mtimes). When `None`, it returns `list[tuple[SFTPAttributes, str]]` as
before — preserving backward compatibility.

The sensor stores `dir_mtimes` in the cursor under the reserved key
`"__dir_mtimes"` and passes/persists it across ticks. Missing entries are always
traversed (conservative default).

#### 4. Compile regex once per asset

Replace inline `re.match()` per file per asset with `re.compile()` once per
asset before the file loop.

### Couchdrop sensor

#### 1. Add `min_modified_time` to `files_list_recursive`

New parameter `min_modified_time: str | None = None` (ISO 8601 UTC string).

When set, replace the existing query:

```text
'{folder_id}' in parents and trashed = false
```

with:

```text
'{folder_id}' in parents and trashed = false
  and (mimeType = 'application/vnd.google-apps.folder'
       or modifiedTime > '{min_modified_time}')
```

This returns all folders (needed for recursion — folder `modifiedTime` does not
update when children change) but only recently modified files. One API call per
folder, same as today, just filtered.

When `min_modified_time` is `None`, the current query is preserved.

#### 2. Compute and pass min cursor from sensor

The sensor computes `min(cursor.values(), default=0)`, converts to ISO 8601 UTC
string, and passes as `min_modified_time` to `files_list_recursive()`.

## Files modified

| File                                                                    | Change                                                                                        |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `src/teamster/libraries/ssh/resources.py`                               | Add `min_mtime` and `dir_mtimes` params to `listdir_attr_r` / `_inner_listdir_attr_r`         |
| `src/teamster/libraries/google/drive/resources.py`                      | Add `min_modified_time` param to `files_list_recursive`, update query                         |
| `src/teamster/code_locations/kipptaf/adp/workforce_now/sftp/sensors.py` | Pass `exclude_dirs`, `min_mtime`, `dir_mtimes`; compile regex; persist `dir_mtimes` in cursor |
| `src/teamster/libraries/couchdrop/sensors.py`                           | Compute min cursor timestamp, pass as `min_modified_time`                                     |

## Risk mitigation

- `min_mtime` and `dir_mtimes` default to `None` — existing callers (assets,
  other sensors) are unaffected.
- `min_modified_time` defaults to `None` — existing query preserved when not
  passed.
- Dir mtime caching is conservative: missing entries are always traversed.
- If dir mtime caching causes missed files (e.g., SFTP server clock skew),
  removing `"__dir_mtimes"` from the cursor resets it.
- All view reversions are parameter-level — remove the new args to revert.

## Testing plan

1. `uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions`
   — confirms no import/wiring errors.
2. Unit test `_inner_listdir_attr_r` with mock `SFTPClient` — verify `min_mtime`
   filtering, `dir_mtimes` caching, and `exclude_dirs` all work.
3. Unit test `files_list_recursive` with mock Drive API — verify the combined
   query returns folders + only recent files.
4. Deploy to branch deployment and monitor sensor tick durations via Dagster
   Cloud UI — confirm both sensors complete well under 300s.
