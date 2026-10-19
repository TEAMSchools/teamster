"""Flag SQL syntax banned by rule S1 (docs/reference/dbt-conventions.md).

Usage: uv run scripts/check_sql_banned_syntax.py <file.sql> [...]

Prints `path:line:col: [error] message (code)` per hit for trunk's regex parser
and exits 1 when any file has a hit.
"""

import re
import sys

# Comments, string literals, and quoted identifiers never hold banned syntax.
_SKIP = re.compile(
    r"\{#.*?#\}|/\*.*?\*/|--[^\n]*|#[^\n]*"
    r"|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`[^`]*`",
    re.S,
)

_BANNED = [
    (
        re.compile(r"\bqualify\b", re.I),
        "S1-qualify",
        "qualify is banned; rank in a CTE, filter with where",
    ),
    (
        re.compile(r"\bgroup\s+by\s+all\b", re.I),
        "S1-group-by-all",
        "group by all is banned; name every group by column",
    ),
    (
        re.compile(r"\bcorresponding\b", re.I),
        "S1-corresponding",
        "union corresponding is banned; list the same columns in each branch",
    ),
]


def _blank(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group())


def find_banned(sql: str) -> list[tuple[int, int, str, str]]:
    """Return (line, col, code, message) for each banned construct, 1-based."""
    code_only = _SKIP.sub(_blank, sql)
    hits = []
    for pattern, code, message in _BANNED:
        for match in pattern.finditer(code_only):
            start = match.start()
            line = code_only.count("\n", 0, start) + 1
            col = start - code_only.rfind("\n", 0, start)
            hits.append((line, col, code, message))
    return sorted(hits)


def main(paths: list[str]) -> int:
    found = False
    for path in paths:
        with open(path) as f:
            for line, col, code, message in find_banned(f.read()):
                found = True
                print(f"{path}:{line}:{col}: [error] {message} ({code})")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
