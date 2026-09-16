"""Build deliberately-broken copies of a workbook, to prove an assertion has teeth.

An assertion that has only ever passed proves nothing. Mutate the *output* you
just produced, in a way a real mistake would produce, and confirm the assertion
fails. In this project that exercise found four separate holes in assertions that
were already passing: a duplicated zone, a re-parented zone, a reordered zone and
a card nested inside a sibling card.

Text surgery, deliberately, not ElementTree. An ET round trip rewrites attribute
quoting and line endings enough to fail a regex-based assertion on an UNMUTATED
file, so ET-built mutants test nothing. Always run `control` first and confirm it
is byte-identical to the source.

Usage:
    uv run python mutate.py <src.twb> <out.twb> "<dashboard>" <op> [args...]

Operations:
    control                          copy unchanged; must be byte-identical
    duplicate   <zone> <before>      leave a stale copy of <zone> before <before>
    reparent    <zone> <new-parent>  move <zone> to be the first child of another
    move-after  <zone> <sibling>     reorder <zone> to sit after <sibling>
    swap        <zone-a> <zone-b>    exchange two zones' positions
    set-attr    <zone> <attr> <val>  change one attribute on the zone tag
    set-format  <zone> <attr> <val>  change one <format> in the zone's own <zone-style>
    delete      <zone>               remove a zone and its subtree

Zones only, inside one dashboard. A tooltip, pane order, manifest entry or
default-format mutant is hand-written.
"""

import re
import sys
from pathlib import Path
from typing import NoReturn

# NOT <zone\b -- the hyphen in <zone-style> is a word boundary, so \b matches it,
# inflates the depth count and never closes.
TAG = re.compile(r"<zone(?=[\s>])[^>]*>|</zone>")


def fail(msg: str) -> NoReturn:
    sys.exit(f"FAIL: {msg}")


def dashboard_span(text: str, name: str) -> tuple[int, int]:
    i = text.index(f"name='{name}'>")
    return i, text.index("</dashboard>", i)


def zone_span(text: str, zid: str, start: int = 0) -> tuple[int, int]:
    """(start, end) of the whole <zone id='zid'>...</zone> subtree, indent included."""
    m = re.search(rf"[ \t]*<zone [^>]*id='{zid}'[^>]*>", text[start:])
    if not m:
        fail(f"zone {zid} not found")
    a = start + m.start()
    open_end = start + m.end()
    if text[open_end - 2 : open_end] == "/>":
        return a, open_end
    depth, pos = 1, open_end
    while depth:
        t = TAG.search(text, pos)
        if not t:
            fail(f"unbalanced zone {zid}")
        tok = t.group(0)
        depth += -1 if tok == "</zone>" else (0 if tok.endswith("/>") else 1)
        pos = t.end()
    return a, pos


def apply_op(d: str, op: str, args: list[str]) -> str:
    if op == "control":
        return d

    if op == "duplicate":
        zid, before = args
        s, e = zone_span(d, zid)
        blk = d[s:e]
        k, _ = zone_span(d, before)
        return d[:k] + blk + "\r\n" + d[k:]

    if op == "reparent":
        zid, parent = args
        s, e = zone_span(d, zid)
        blk = d[s:e]
        d = d[:s] + d[e:]
        p_start, _ = zone_span(d, parent)
        insert = d.index(">", p_start) + 1
        return d[:insert] + "\r\n" + blk + d[insert:]

    if op == "move-after":
        zid, sib = args
        s, e = zone_span(d, zid)
        blk = d[s:e]
        d = d[:s] + d[e:]
        _, k = zone_span(d, sib)
        return d[:k] + "\r\n" + blk + d[k:]

    if op == "swap":
        a_id, b_id = args
        a_s, a_e = zone_span(d, a_id)
        b_s, b_e = zone_span(d, b_id)
        if a_s > b_s:
            a_id, b_id = b_id, a_id
            a_s, a_e, b_s, b_e = b_s, b_e, a_s, a_e
        if a_e > b_s:
            fail(f"zones {a_id} and {b_id} overlap; cannot swap")
        return d[:a_s] + d[b_s:b_e] + d[a_e:b_s] + d[a_s:a_e] + d[b_e:]

    if op == "set-attr":
        zid, attr, val = args
        m = re.search(rf"<zone [^>]*id='{zid}'[^>]*>", d)
        if not m:
            fail(f"zone {zid} not found")
        tag = m.group(0)
        new = (
            re.sub(rf"{attr}='[^']*'", f"{attr}='{val}'", tag)
            if f"{attr}='" in tag
            else tag[:-1] + f" {attr}='{val}'>"
        )
        return d[: m.start()] + new + d[m.end() :]

    if op == "set-format":
        # A zone's own <zone-style> is the LAST one inside its span: the content
        # model puts child zones before the container's own style, so children's
        # styles all appear earlier.
        zid, attr, val = args
        s, e = zone_span(d, zid)
        span = d[s:e]
        styles = list(re.finditer(r"<zone-style>.*?</zone-style>", span, re.S))
        if not styles:
            fail(f"zone {zid} has no <zone-style>")
        blk = styles[-1]
        body = blk.group(0)
        new, n = re.subn(
            rf"(<format attr='{attr}' value=')[^']*(')", rf"\g<1>{val}\g<2>", body
        )
        if n == 0:
            fail(f"zone {zid} style has no format attr={attr!r}")
        return d[:s] + span[: blk.start()] + new + span[blk.end() :] + d[e:]

    if op == "delete":
        (zid,) = args
        s, e = zone_span(d, zid)
        return d[:s] + d[e:]

    fail(f"unknown operation {op!r}")


def main(argv: list[str]) -> None:
    if len(argv) < 4:
        sys.exit(__doc__)
    src, out, dash, op, args = (
        Path(argv[0]),
        Path(argv[1]),
        argv[2],
        argv[3],
        argv[4:],
    )
    text = src.read_text(encoding="utf-8", newline="")
    i, j = dashboard_span(text, dash)
    result = text[:i] + apply_op(text[i:j], op, args) + text[j:]
    out.write_text(result, encoding="utf-8", newline="")

    same = result == text
    note = " (byte-identical -- surgery is lossless)" if same else ""
    if op == "control" and not same:
        fail("control output differs from the source; every mutant result is void")
    if op != "control" and same:
        fail(f"{op} changed nothing; the mutant is not testing anything")
    print(f"  wrote {out.name}: {op} {' '.join(args)}{note}")


if __name__ == "__main__":
    main(sys.argv[1:])
