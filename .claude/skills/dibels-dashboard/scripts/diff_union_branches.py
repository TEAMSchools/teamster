"""Compare the three UNION ALL branches' projections by ordinal.

Paren/bracket-aware split of each branch's select list, so multi-line
coalesce/case expressions count as one projection. Prints the first ordinal
where the aliases disagree.
"""

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
sql = path.read_text(encoding="utf-8", newline="")

# strip line comments and jinja comment blocks: both otherwise parse as
# projections and desynchronise every ordinal after them
sql = re.sub(r"\{#-?.*?-?#\}", "", sql, flags=re.DOTALL)
sql = re.sub(r"(?m)^\s*--.*$", "", sql)
sql = re.sub(r"--[^\n]*", "", sql)

# split on top-level `union all` at column 0
parts = re.split(r"(?m)^union all\s*$", sql)
print(f"branches: {len(parts)}")


def projections(chunk: str) -> list[str]:
    # take from the LAST top-level `select` to the matching `from` at column 0
    m = list(re.finditer(r"(?m)^select\s*$", chunk))
    if not m:
        return []
    body = chunk[m[-1].end() :]
    fm = re.search(r"(?m)^from\s", body)
    if fm:
        body = body[: fm.start()]

    out, buf, depth, quote = [], [], 0, None
    for ch in body:
        if quote:
            # a comma inside 'On Aimline, Below Benchmark' is not a separator
            if ch == quote:
                quote = None
            buf.append(ch)
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(" ".join("".join(buf).split()))
            buf = []
        else:
            buf.append(ch)
    tail = " ".join("".join(buf).split())
    if tail:
        out.append(tail)
    return [p for p in out if p]


def alias(proj: str) -> str:
    m = re.search(r"\bas\s+([A-Za-z0-9_`]+)\s*$", proj)
    if m:
        return m.group(1).strip("`")
    return proj.split(".")[-1].strip("`")


lists = [projections(p) for p in parts]
for n, lst in enumerate(lists, 1):
    print(f"  branch {n}: {len(lst)} projections")

width = max(len(x) for x in lists)
mismatch = 0
for i in range(width):
    names = [(lst[i] if i < len(lst) else "<MISSING>") for lst in lists]
    al = [alias(x) if x != "<MISSING>" else x for x in names]
    if len(set(al)) != 1:
        mismatch += 1
        if mismatch <= 6:
            print(f"  ordinal {i + 1}: " + " | ".join(al))

print(f"total mismatched ordinals: {mismatch}")

if len(sys.argv) > 2:
    lo, hi = (int(x) for x in sys.argv[2].split("-"))
    print(f"\n--- ordinals {lo}-{hi} ---")
    for i in range(lo - 1, hi):
        for n, lst in enumerate(lists, 1):
            val = lst[i] if i < len(lst) else "<MISSING>"
            print(f"  {i + 1:>3} b{n}: {val[:95]}")
        print()
