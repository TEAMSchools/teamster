"""Prove a SQL edit is comment-only by comparing comment-stripped tokens.

Usage: comment_only_diff.py OLD_SQL NEW_SQL

To compare against main:
git -C <worktree> show origin/main:<path> > <scratchpad>/old.sql

String literals are compared byte for byte; whitespace collapses only outside
them. BigQuery `#` comments are not stripped, so they report LOGIC CHANGE.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

QUOTES = "'\"`"
TRIPLES = ("'''", '"""')


def _literal_end(sql: str, i: int) -> int:
    """Index just past the string literal that starts at i."""
    for triple in TRIPLES:
        if sql.startswith(triple, i):
            end = sql.find(triple, i + 3)
            return len(sql) if end == -1 else end + 3
    quote = sql[i]
    j = i + 1
    while j < len(sql):
        if sql[j] == "\\":
            j += 2
            continue
        if sql[j] == quote:
            return j + 1
        j += 1
    return len(sql)


def strip_comments(sql: str) -> str:
    code: list[str] = []
    parts: list[str] = []
    i, n = 0, len(sql)

    def flush() -> None:
        if code:
            parts.append(re.sub(r"\s+", " ", "".join(code)))
            code.clear()

    while i < n:
        if sql[i] in QUOTES:
            end = _literal_end(sql, i)
            flush()
            parts.append(sql[i:end])
            i = end
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end == -1 else end
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
            code.append(" ")
        elif sql.startswith("{#", i):
            end = sql.find("#}", i + 2)
            i = n if end == -1 else end + 2
            code.append(" ")
        else:
            code.append(sql[i])
            i += 1
    flush()
    return "".join(parts).strip()


def is_comment_only(old: str, new: str) -> bool:
    return strip_comments(old) == strip_comments(new)


def main(argv: list[str]) -> int:
    old, new = Path(argv[1]).read_text(), Path(argv[2]).read_text()
    if is_comment_only(old, new):
        print("comment-only")
        return 0
    print("LOGIC CHANGE")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
