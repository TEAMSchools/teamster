"""Passive audit of SFTP directory mtime propagation.

If a directory's ``st_mtime`` is older than the max ``st_mtime`` of its
children, the server doesn't advance dir mtime on entry changes. Sensors
using ``listdir_attr_r(dir_mtimes=)`` against such a server silently drop
data (see #3972).

Each parametrized test connects to one SFTP server, walks a bounded portion
of the tree, and fails if it finds any directory whose ``st_mtime`` is older
than its newest child. Absence of a smoking gun is suggestive but not proof
of propagation; the test is intended as a forward-looking opt-in safety
check, not a positive guarantee.

Requires the credentials bootstrapped by ``tests/conftest.py``. Per-server
skip when the relevant environment variables are unset.
"""

from collections import deque
from dataclasses import dataclass
from stat import S_ISDIR, S_ISREG

import pytest
from dagster import build_resources
from dagster_shared import check
from paramiko import SFTPClient

# Bounded walk to keep each server's test under a minute or so.
_MAX_DIRS = 200
_MAX_DEPTH = 4


@dataclass(frozen=True)
class _Violation:
    dir_path: str
    dir_mtime: float
    child_path: str
    child_mtime: float


def _normalize(path: str) -> str:
    return path.rstrip("/") or path


def _join(parent: str, name: str) -> str:
    return f"{_normalize(parent)}/{name}"


def _walk(
    sftp: SFTPClient,
    root: str,
    exclude: frozenset[str],
    max_dirs: int,
    max_depth: int,
) -> list[_Violation]:
    """BFS the tree under ``root``; collect dir-mtime propagation violations.

    The root directory itself is not audited — only its descendants — because
    we can't observe root's own ``st_mtime`` via ``listdir_attr`` without
    statting it from a hypothetical parent. Servers with stale root mtimes
    will surface elsewhere in the tree as long as the prune would ever
    recurse past root.
    """
    violations: list[_Violation] = []
    queue: deque[tuple[str, float, int]] = deque()

    try:
        root_entries = sftp.listdir_attr(root)
    except OSError:
        return violations

    for entry in root_entries:
        if entry.filename in (".", ".."):
            continue
        if not S_ISDIR(check.not_none(value=entry.st_mode)):
            continue
        path = _join(root, entry.filename)
        if path in exclude:
            continue
        queue.append((path, check.not_none(value=entry.st_mtime), 0))

    visited = 0
    while queue and visited < max_dirs:
        dir_path, dir_mtime, depth = queue.popleft()
        visited += 1

        try:
            children = sftp.listdir_attr(dir_path)
        except OSError:
            continue

        max_child_mtime = 0.0
        max_child_path = ""
        for child in children:
            mode = check.not_none(value=child.st_mode)
            if not (S_ISREG(mode) or S_ISDIR(mode)):
                continue
            mtime = check.not_none(value=child.st_mtime)
            if mtime > max_child_mtime:
                max_child_mtime = mtime
                max_child_path = _join(dir_path, child.filename)
            if S_ISDIR(mode) and depth + 1 < max_depth:
                sub_path = _join(dir_path, child.filename)
                if sub_path not in exclude:
                    queue.append((sub_path, mtime, depth + 1))

        if max_child_mtime > dir_mtime:
            violations.append(
                _Violation(
                    dir_path=dir_path,
                    dir_mtime=dir_mtime,
                    child_path=max_child_path,
                    child_mtime=max_child_mtime,
                )
            )

    return violations


def test_dir_mtime_propagates(sftp_server) -> None:
    """Server should advance directory ``st_mtime`` on child changes."""
    with build_resources({"ssh": sftp_server.builder()}) as resources:
        with (
            resources.ssh.get_connection() as connection,
            connection.open_sftp() as sftp,
        ):
            violations = _walk(
                sftp=sftp,
                root=sftp_server.remote_dir,
                exclude=frozenset(sftp_server.exclude_dirs),
                max_dirs=_MAX_DIRS,
                max_depth=_MAX_DEPTH,
            )

    if violations:
        sample = "\n".join(
            f"  {v.dir_path!r} mtime={v.dir_mtime} < child {v.child_path!r} "
            f"mtime={v.child_mtime}"
            for v in violations[:5]
        )
        pytest.fail(
            f"{sftp_server.name}: {len(violations)} directory mtime propagation "
            f"violation(s) (showing up to 5):\n{sample}\n"
            "Do not pass `dir_mtimes=` to listdir_attr_r for this server."
        )
