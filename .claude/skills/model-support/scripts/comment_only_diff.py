"""Prove a SQL edit is comment-only by comparing comment-stripped tokens.

Usage: comment_only_diff.py OLD_SQL NEW_SQL

To compare against main:
git -C <worktree> show origin/main:<path> > <scratchpad>/old.sql
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

QUOTES = "'\"`"


def strip_comments(sql: str) -> str:
    out: list[str] = []
    i, n = 0, len(sql)
    quote: str | None = None
    while i < n:
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(sql[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
        elif ch in QUOTES:
            quote = ch
            out.append(ch)
            i += 1
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end == -1 else end
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
        elif sql.startswith("{#", i):
            end = sql.find("#}", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
        else:
            out.append(ch)
            i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


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
