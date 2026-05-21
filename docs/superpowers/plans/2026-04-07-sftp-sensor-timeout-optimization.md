# SFTP Sensor Timeout Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize two kipptaf sensors
(`kipptaf__adp__workforce_now__sftp_assets_sensor` and
`kipptaf__couchdrop__sftp_asset_job_sensor`) to avoid 300s execution timeouts by
adding incremental filtering to their recursive directory listings.

**Architecture:** Add `min_mtime` and `dir_mtimes` parameters to
`SSHResource._inner_listdir_attr_r` for server-side file skipping and
directory-level caching. Add `min_modified_time` parameter to
`GoogleDriveResource.files_list_recursive` to filter files via the Drive API
query. Update both sensors to compute and pass these filters from their cursors.

**Tech Stack:** Python 3.13, Dagster, paramiko (SFTP), Google Drive API v3,
pytest

**Spec:**
`docs/superpowers/specs/2026-04-07-sftp-sensor-timeout-optimization-design.md`

---

## Task 1: Add `min_mtime` to `SSHResource._inner_listdir_attr_r`

**Files:**

- Modify: `src/teamster/libraries/ssh/resources.py:15-58`
- Test: `tests/resources/test_resource_ssh_listdir.py`

- [ ] **Step 1: Write the failing test for `min_mtime` filtering**

Create `tests/resources/test_resource_ssh_listdir.py`:

```python
from unittest.mock import MagicMock, patch

from paramiko import SFTPAttributes

from teamster.libraries.ssh.resources import SSHResource


def _make_sftp_attr(
    filename: str, st_mode: int, st_mtime: int, st_size: int
) -> SFTPAttributes:
    attr = SFTPAttributes()
    attr.filename = filename
    attr.st_mode = st_mode
    attr.st_mtime = st_mtime
    attr.st_size = st_size
    return attr


# regular file mode
FILE_MODE = 0o100644
# directory mode
DIR_MODE = 0o40755


def _build_ssh_resource() -> SSHResource:
    resource = SSHResource(remote_host="fake-host")
    resource.log = MagicMock()
    return resource


def _build_mock_sftp(dir_tree: dict) -> MagicMock:
    """Build a mock SFTPClient from a directory tree dict.

    Args:
        dir_tree: Nested dict where keys are dir paths and values are lists of
            SFTPAttributes. Use nested dicts for subdirectories.
    """
    sftp = MagicMock()

    def listdir_attr(path: str) -> list[SFTPAttributes]:
        return dir_tree.get(path, [])

    sftp.listdir_attr.side_effect = listdir_attr
    return sftp


def test_min_mtime_filters_old_files():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("old.csv", FILE_MODE, st_mtime=100, st_size=50),
                _make_sftp_attr("new.csv", FILE_MODE, st_mtime=300, st_size=50),
            ],
        }
    )
    resource = _build_ssh_resource()

    files = resource._inner_listdir_attr_r(
        sftp_client=sftp, remote_dir=".", exclude_dirs=[], min_mtime=200,
    )

    filenames = [attr.filename for attr, _ in files]
    assert filenames == ["new.csv"]


def test_min_mtime_none_returns_all_files():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("old.csv", FILE_MODE, st_mtime=100, st_size=50),
                _make_sftp_attr("new.csv", FILE_MODE, st_mtime=300, st_size=50),
            ],
        }
    )
    resource = _build_ssh_resource()

    files = resource._inner_listdir_attr_r(
        sftp_client=sftp, remote_dir=".", exclude_dirs=[],
    )

    filenames = [attr.filename for attr, _ in files]
    assert filenames == ["old.csv", "new.csv"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run pytest tests/resources/test_resource_ssh_listdir.py -v`

Expected: FAIL — `_inner_listdir_attr_r` does not accept `min_mtime` parameter.

- [ ] **Step 3: Implement `min_mtime` in `_inner_listdir_attr_r` and
      `listdir_attr_r`**

In `src/teamster/libraries/ssh/resources.py`, replace `listdir_attr_r` and
`_inner_listdir_attr_r`:

```python
def listdir_attr_r(
    self,
    remote_dir: str = ".",
    exclude_dirs: list[str] | None = None,
    min_mtime: float | None = None,
):
    if exclude_dirs is None:
        exclude_dirs = []

    with self.get_connection() as connection:
        self.log.info("Opening SFTP session")
        with connection.open_sftp() as sftp_client:
            self.log.info(f"Listing of all files under {remote_dir}")
            return self._inner_listdir_attr_r(
                sftp_client=sftp_client,
                remote_dir=remote_dir,
                exclude_dirs=exclude_dirs,
                min_mtime=min_mtime,
            )

def _inner_listdir_attr_r(
    self,
    sftp_client: SFTPClient,
    remote_dir: str,
    exclude_dirs: list[str],
    files: list | None = None,
    min_mtime: float | None = None,
) -> list[tuple[SFTPAttributes, str]]:
    if files is None:
        files = []

    if remote_dir in exclude_dirs:
        return files

    self.log.info(f"Listing {remote_dir}")
    for file in sftp_client.listdir_attr(remote_dir):
        path = str(pathlib.Path(remote_dir) / file.filename)

        if S_ISDIR(check.not_none(value=file.st_mode)):
            self._inner_listdir_attr_r(
                sftp_client=sftp_client,
                remote_dir=path,
                exclude_dirs=exclude_dirs,
                files=files,
                min_mtime=min_mtime,
            )
        elif S_ISREG(check.not_none(value=file.st_mode)):
            if min_mtime is None or file.st_mtime > min_mtime:
                files.append((file, path))

    return files
```

- [ ] **Step 4: Run test to verify it passes**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run pytest tests/resources/test_resource_ssh_listdir.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization
git add tests/resources/test_resource_ssh_listdir.py src/teamster/libraries/ssh/resources.py
git commit -m "feat(ssh): add min_mtime filter to listdir_attr_r"
```

---

## Task 2: Add `dir_mtimes` caching to `SSHResource._inner_listdir_attr_r`

**Files:**

- Modify: `src/teamster/libraries/ssh/resources.py:15-58`
- Test: `tests/resources/test_resource_ssh_listdir.py`

- [ ] **Step 1: Write the failing tests for `dir_mtimes` caching**

Append to `tests/resources/test_resource_ssh_listdir.py`:

```python
def test_dir_mtimes_skips_unchanged_subtree():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("subdir", DIR_MODE, st_mtime=100, st_size=0),
            ],
            "subdir": [
                _make_sftp_attr("file.csv", FILE_MODE, st_mtime=150, st_size=50),
            ],
        }
    )
    resource = _build_ssh_resource()

    # dir_mtimes says subdir was last seen at mtime=100 — unchanged, skip it
    files, updated_dir_mtimes = resource._inner_listdir_attr_r(
        sftp_client=sftp,
        remote_dir=".",
        exclude_dirs=[],
        dir_mtimes={"subdir": 100},
    )

    assert files == []
    assert updated_dir_mtimes["subdir"] == 100
    # subdir should NOT have been listed
    sftp.listdir_attr.assert_called_once_with(".")


def test_dir_mtimes_traverses_changed_subtree():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("subdir", DIR_MODE, st_mtime=200, st_size=0),
            ],
            "subdir": [
                _make_sftp_attr("file.csv", FILE_MODE, st_mtime=250, st_size=50),
            ],
        }
    )
    resource = _build_ssh_resource()

    # dir_mtimes says subdir was last seen at mtime=100 — changed, traverse it
    files, updated_dir_mtimes = resource._inner_listdir_attr_r(
        sftp_client=sftp,
        remote_dir=".",
        exclude_dirs=[],
        dir_mtimes={"subdir": 100},
    )

    filenames = [attr.filename for attr, _ in files]
    assert filenames == ["file.csv"]
    assert updated_dir_mtimes["subdir"] == 200


def test_dir_mtimes_traverses_unseen_directory():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("newdir", DIR_MODE, st_mtime=300, st_size=0),
            ],
            "newdir": [
                _make_sftp_attr("data.csv", FILE_MODE, st_mtime=350, st_size=50),
            ],
        }
    )
    resource = _build_ssh_resource()

    # empty dir_mtimes — newdir is unseen, must traverse
    files, updated_dir_mtimes = resource._inner_listdir_attr_r(
        sftp_client=sftp,
        remote_dir=".",
        exclude_dirs=[],
        dir_mtimes={},
    )

    filenames = [attr.filename for attr, _ in files]
    assert filenames == ["data.csv"]
    assert updated_dir_mtimes["newdir"] == 300


def test_dir_mtimes_none_returns_list_only():
    """When dir_mtimes is None, return type is list (backward compat)."""
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("file.csv", FILE_MODE, st_mtime=100, st_size=50),
            ],
        }
    )
    resource = _build_ssh_resource()

    result = resource._inner_listdir_attr_r(
        sftp_client=sftp, remote_dir=".", exclude_dirs=[],
    )

    assert isinstance(result, list)
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run pytest tests/resources/test_resource_ssh_listdir.py -v -k dir_mtimes`

Expected: FAIL — `_inner_listdir_attr_r` does not accept `dir_mtimes` parameter.

- [ ] **Step 3: Implement `dir_mtimes` caching**

In `src/teamster/libraries/ssh/resources.py`, update both methods:

```python
def listdir_attr_r(
    self,
    remote_dir: str = ".",
    exclude_dirs: list[str] | None = None,
    min_mtime: float | None = None,
    dir_mtimes: dict[str, float] | None = None,
) -> (
    tuple[list[tuple[SFTPAttributes, str]], dict[str, float]]
    | list[tuple[SFTPAttributes, str]]
):
    if exclude_dirs is None:
        exclude_dirs = []

    with self.get_connection() as connection:
        self.log.info("Opening SFTP session")
        with connection.open_sftp() as sftp_client:
            self.log.info(f"Listing of all files under {remote_dir}")
            return self._inner_listdir_attr_r(
                sftp_client=sftp_client,
                remote_dir=remote_dir,
                exclude_dirs=exclude_dirs,
                min_mtime=min_mtime,
                dir_mtimes=dir_mtimes,
            )

def _inner_listdir_attr_r(
    self,
    sftp_client: SFTPClient,
    remote_dir: str,
    exclude_dirs: list[str],
    files: list | None = None,
    min_mtime: float | None = None,
    dir_mtimes: dict[str, float] | None = None,
) -> (
    tuple[list[tuple[SFTPAttributes, str]], dict[str, float]]
    | list[tuple[SFTPAttributes, str]]
):
    if files is None:
        files = []

    if remote_dir in exclude_dirs:
        if dir_mtimes is not None:
            return files, dir_mtimes
        return files

    self.log.info(f"Listing {remote_dir}")
    for file in sftp_client.listdir_attr(remote_dir):
        path = str(pathlib.Path(remote_dir) / file.filename)

        if S_ISDIR(check.not_none(value=file.st_mode)):
            if dir_mtimes is not None:
                cached_mtime = dir_mtimes.get(path)
                if cached_mtime is not None and file.st_mtime <= cached_mtime:
                    continue
                dir_mtimes[path] = file.st_mtime

            self._inner_listdir_attr_r(
                sftp_client=sftp_client,
                remote_dir=path,
                exclude_dirs=exclude_dirs,
                files=files,
                min_mtime=min_mtime,
                dir_mtimes=dir_mtimes,
            )
        elif S_ISREG(check.not_none(value=file.st_mode)):
            if min_mtime is None or file.st_mtime > min_mtime:
                files.append((file, path))

    if dir_mtimes is not None:
        return files, dir_mtimes
    return files
```

Note: `_inner_listdir_attr_r` is recursive and mutates `files` and `dir_mtimes`
in place. The return type branching only matters at the top-level call. The
recursive calls' return values are ignored (the caller already holds references
to the mutable `files` and `dir_mtimes` objects).

- [ ] **Step 4: Run all tests to verify they pass**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run pytest tests/resources/test_resource_ssh_listdir.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization
git add tests/resources/test_resource_ssh_listdir.py src/teamster/libraries/ssh/resources.py
git commit -m "feat(ssh): add dir_mtimes caching to listdir_attr_r"
```

---

## Task 3: Update ADP WFN SFTP sensor

**Files:**

- Modify:
  `src/teamster/code_locations/kipptaf/adp/workforce_now/sftp/sensors.py:1-74`

- [ ] **Step 1: Update the sensor to use all new parameters**

Replace the full contents of
`src/teamster/code_locations/kipptaf/adp/workforce_now/sftp/sensors.py`:

```python
import json
import re
from datetime import datetime

from dagster import (
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from dagster_shared import check

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_now.sftp.assets import assets
from teamster.libraries.ssh.resources import SSHResource

DIR_MTIMES_KEY = "__dir_mtimes"


@sensor(
    name=f"{CODE_LOCATION}__adp__workforce_now__sftp_assets_sensor",
    target=assets,
    minimum_interval_seconds=(60 * 10),
)
def adp_wfn_sftp_sensor(
    context: SensorEvaluationContext, ssh_adp_workforce_now: SSHResource
):
    now = datetime.now(LOCAL_TIMEZONE)

    run_requests = []
    cursor: dict = json.loads(context.cursor or "{}")

    dir_mtimes = cursor.pop(DIR_MTIMES_KEY, {})

    asset_cursors = {k: v for k, v in cursor.items() if k != DIR_MTIMES_KEY}
    min_mtime = min(asset_cursors.values(), default=0)

    files, dir_mtimes = ssh_adp_workforce_now.listdir_attr_r(
        exclude_dirs=["./payroll"],
        min_mtime=min_mtime,
        dir_mtimes=dir_mtimes,
    )

    for asset in assets:
        asset_metadata = asset.metadata_by_key[asset.key]
        asset_identifier = asset.key.to_python_identifier()

        context.log.info(asset_identifier)
        last_run = cursor.get(asset_identifier, 0)

        pattern = re.compile(pattern=asset_metadata["remote_file_regex"])

        updates = []
        for f, _ in files:
            match = pattern.match(string=f.filename)

            if (
                match is not None
                and f.st_mtime > last_run
                and check.not_none(value=f.st_size) > 0
            ):
                context.log.info(f"{f.filename}: {f.st_mtime} - {f.st_size}")
                updates.append({"mtime": f.st_mtime})

        if updates:
            for u in updates:
                run_requests.append(
                    RunRequest(
                        run_key=f"{asset_identifier}_{u['mtime']}",
                        asset_selection=[asset.key],
                    )
                )

            cursor[asset_identifier] = now.timestamp()

    cursor[DIR_MTIMES_KEY] = dir_mtimes

    if run_requests:
        return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))
    else:
        return SkipReason()


sensors = [
    adp_wfn_sftp_sensor,
]
```

Key changes from original:

- `DIR_MTIMES_KEY` constant for the cursor key
- `cursor.pop(DIR_MTIMES_KEY, {})` extracts dir_mtimes before computing
  `min_mtime`
- `min_mtime = min(asset_cursors.values(), default=0)` computes global minimum
- `listdir_attr_r` called with `exclude_dirs`, `min_mtime`, and `dir_mtimes`
- `re.compile()` per asset before the file loop (was inline `re.match()`)
- `cursor[DIR_MTIMES_KEY] = dir_mtimes` persists dir_mtimes back

- [ ] **Step 2: Validate Dagster definitions**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions`

Expected: Validation passes (or env var errors unrelated to this change).

- [ ] **Step 3: Commit**

```bash
cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization
git add src/teamster/code_locations/kipptaf/adp/workforce_now/sftp/sensors.py
git commit -m "perf(adp): optimize WFN SFTP sensor with min_mtime, dir_mtimes, exclude_dirs"
```

---

## Task 4: Add `min_modified_time` to

`GoogleDriveResource.files_list_recursive`

**Files:**

- Modify: `src/teamster/libraries/google/drive/resources.py:128-183`
- Test: `tests/resources/test_resource_google_drive_listdir.py`

- [ ] **Step 1: Write the failing test**

Create `tests/resources/test_resource_google_drive_listdir.py`:

```python
from unittest.mock import MagicMock

from teamster.libraries.google.drive.resources import GoogleDriveResource


def _build_drive_resource() -> GoogleDriveResource:
    resource = GoogleDriveResource()
    resource._log = MagicMock()
    resource._service = MagicMock()
    return resource


def _mock_files_list(resource: GoogleDriveResource, responses: dict[str, list]):
    """Mock files_list to return different results based on the query.

    Args:
        resource: The GoogleDriveResource to mock.
        responses: Dict mapping folder_id to list of file dicts.
    """
    original_files_list = resource.files_list

    def side_effect(**kwargs) -> list[dict]:
        q = kwargs.get("q", "")

        for folder_id, files in responses.items():
            if f"'{folder_id}' in parents" in q:
                return files

        return []

    resource.files_list = MagicMock(side_effect=side_effect)


COMMON_KWARGS = {
    "corpora": "drive",
    "drive_id": "fake-drive-id",
    "include_items_from_all_drives": True,
    "supports_all_drives": True,
    "fields": "files(id,name,mimeType,modifiedTime,size)",
}


def test_min_modified_time_filters_old_files():
    resource = _build_drive_resource()

    _mock_files_list(
        resource,
        {
            "root-folder": [
                {
                    "id": "f1",
                    "name": "old.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2026-01-01T00:00:00.000Z",
                    "size": "100",
                },
                {
                    "id": "f2",
                    "name": "new.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2026-04-01T00:00:00.000Z",
                    "size": "200",
                },
            ],
        },
    )

    files = resource.files_list_recursive(
        **COMMON_KWARGS,
        folder_id="root-folder",
        file_path="/test",
        min_modified_time="2026-03-01T00:00:00.000Z",
    )

    assert len(files) == 1
    assert files[0]["name"] == "new.csv"


def test_min_modified_time_preserves_folders():
    resource = _build_drive_resource()

    _mock_files_list(
        resource,
        {
            "root-folder": [
                {
                    "id": "subfolder",
                    "name": "subdir",
                    "mimeType": "application/vnd.google-apps.folder",
                    "modifiedTime": "2025-01-01T00:00:00.000Z",
                    "size": "0",
                },
            ],
            "subfolder": [
                {
                    "id": "f1",
                    "name": "recent.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2026-04-01T00:00:00.000Z",
                    "size": "100",
                },
            ],
        },
    )

    files = resource.files_list_recursive(
        **COMMON_KWARGS,
        folder_id="root-folder",
        file_path="/test",
        min_modified_time="2026-03-01T00:00:00.000Z",
    )

    assert len(files) == 1
    assert files[0]["name"] == "recent.csv"
    assert files[0]["path"] == "/test/subdir/recent.csv"


def test_min_modified_time_none_returns_all():
    resource = _build_drive_resource()

    _mock_files_list(
        resource,
        {
            "root-folder": [
                {
                    "id": "f1",
                    "name": "old.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2025-01-01T00:00:00.000Z",
                    "size": "100",
                },
                {
                    "id": "f2",
                    "name": "new.csv",
                    "mimeType": "text/csv",
                    "modifiedTime": "2026-04-01T00:00:00.000Z",
                    "size": "200",
                },
            ],
        },
    )

    files = resource.files_list_recursive(
        **COMMON_KWARGS,
        folder_id="root-folder",
        file_path="/test",
    )

    assert len(files) == 2


def test_min_modified_time_query_construction():
    """Verify the Drive API query includes the combined filter."""
    resource = _build_drive_resource()

    _mock_files_list(resource, {"root-folder": []})

    resource.files_list_recursive(
        **COMMON_KWARGS,
        folder_id="root-folder",
        file_path="/test",
        min_modified_time="2026-03-01T00:00:00.000Z",
    )

    call_kwargs = resource.files_list.call_args_list[0].kwargs
    expected_q = (
        "'root-folder' in parents and trashed = false"
        " and (mimeType = 'application/vnd.google-apps.folder'"
        " or modifiedTime > '2026-03-01T00:00:00.000Z')"
    )
    assert call_kwargs["q"] == expected_q
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run pytest tests/resources/test_resource_google_drive_listdir.py -v`

Expected: FAIL — `files_list_recursive` does not accept `min_modified_time`
parameter.

- [ ] **Step 3: Implement `min_modified_time` in `files_list_recursive`**

In `src/teamster/libraries/google/drive/resources.py`, replace
`files_list_recursive`:

```python
def files_list_recursive(
    self,
    corpora: str,
    drive_id: str,
    include_items_from_all_drives: bool,
    supports_all_drives: bool,
    fields: str,
    folder_id: str,
    file_path: str = "",
    exclude: list[str] | None = None,
    files: list | None = None,
    min_modified_time: str | None = None,
) -> list:
    if exclude is None:
        exclude = []

    if files is None:
        files = []

    if file_path in exclude:
        return files

    q = f"'{folder_id}' in parents and trashed = false"
    if min_modified_time is not None:
        q += (
            f" and (mimeType = 'application/vnd.google-apps.folder'"
            f" or modifiedTime > '{min_modified_time}')"
        )

    self._log.info(f"Listing of all files under {file_path}")
    files_list = self.files_list(
        corpora=corpora,
        drive_id=drive_id,
        include_items_from_all_drives=include_items_from_all_drives,
        q=q,
        supports_all_drives=supports_all_drives,
        fields=fields,
    )

    for file in files_list:
        file_subpath = f"{file_path}/{file['name']}"

        if file["mimeType"] == "application/vnd.google-apps.folder":
            self.files_list_recursive(
                corpora=corpora,
                drive_id=drive_id,
                include_items_from_all_drives=include_items_from_all_drives,
                supports_all_drives=supports_all_drives,
                folder_id=file["id"],
                file_path=file_subpath,
                exclude=exclude,
                files=files,
                fields=fields,
                min_modified_time=min_modified_time,
            )
        else:
            file["path"] = f"{file_path}/{file['name']}"
            file["size"] = int(file["size"])
            file["modified_timestamp"] = datetime.strptime(
                file["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).timestamp()

            files.append(file)

    return files
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run pytest tests/resources/test_resource_google_drive_listdir.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization
git add tests/resources/test_resource_google_drive_listdir.py src/teamster/libraries/google/drive/resources.py
git commit -m "feat(drive): add min_modified_time filter to files_list_recursive"
```

---

## Task 5: Update Couchdrop sensor

**Files:**

- Modify: `src/teamster/libraries/couchdrop/sensors.py:61-78`

- [ ] **Step 1: Update the sensor to compute and pass `min_modified_time`**

In `src/teamster/libraries/couchdrop/sensors.py`, replace lines 62-78 (inside
`_sensor`, from `now_timestamp` through the `files = ...` call):

```python
    def _sensor(context: SensorEvaluationContext, google_drive: GoogleDriveResource):
        now_timestamp = datetime.now(local_timezone).timestamp()

        run_request_kwargs = []
        run_requests = []

        cursor: dict = json.loads(context.cursor or "{}")

        min_cursor = min(cursor.values(), default=0)

        if min_cursor > 0:
            min_modified_time = datetime.fromtimestamp(
                min_cursor, tz=UTC
            ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            min_modified_time = None

        files = google_drive.files_list_recursive(
            corpora="drive",
            drive_id="0AKZ2G1Z8rxooUk9PVA",
            include_items_from_all_drives=True,
            supports_all_drives=True,
            fields="files(id,name,mimeType,modifiedTime,size)",
            folder_id=folder_id,
            file_path=f"/data-team/{code_location}",
            exclude=exclude_dirs,
            min_modified_time=min_modified_time,
        )
```

Also add the `UTC` import at the top of the file. Replace line 3:

```python
from datetime import UTC, datetime
```

- [ ] **Step 2: Validate Dagster definitions**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions`

Expected: Validation passes (or env var errors unrelated to this change).

- [ ] **Step 3: Commit**

```bash
cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization
git add src/teamster/libraries/couchdrop/sensors.py
git commit -m "perf(couchdrop): pass min_modified_time to files_list_recursive"
```

---

## Task 6: Final validation and push

- [ ] **Step 1: Run all new unit tests**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run pytest tests/resources/test_resource_ssh_listdir.py tests/resources/test_resource_google_drive_listdir.py -v`

Expected: All PASS

- [ ] **Step 2: Run existing definition validation tests**

Run:
`cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization && uv run pytest tests/test_dagster_definitions.py -v -k kipptaf`

Expected: PASS (or env var errors unrelated to this change)

- [ ] **Step 3: Push branch**

```bash
cd .worktrees/cbini/perf/claude-sftp-sensor-timeout-optimization
git push -u origin cbini/perf/claude-sftp-sensor-timeout-optimization
```
