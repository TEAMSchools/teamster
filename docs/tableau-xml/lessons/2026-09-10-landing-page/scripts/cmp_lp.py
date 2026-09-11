"""Compare the LP elements in the new production base against our out.twb."""

import re
from pathlib import Path

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
new = (LP / "base.twb").read_text(encoding="utf-8", newline="")
out = (LP / "out.twb").read_text(encoding="utf-8", newline="")


def ws_blocks(t):
    return {
        m.group(1): m.group(0)
        for m in re.finditer(r"<worksheet name='([^']*)'>.*?</worksheet>", t, re.S)
    }


def dash_block(t, name):
    m = re.search(
        r"<dashboard[^>]*name='" + re.escape(name) + r"'.*?</dashboard>", t, re.S
    )
    return m.group(0) if m else None


nb, ob = ws_blocks(new), ws_blocks(out)
lp = sorted(k for k in nb if k.startswith("LP - "))
print(f"=== {len(lp)} LP sheets: production rev26 vs our out.twb ===")
same = 0
for k in lp:
    o = ob.get(k)
    if o is None:
        print(f"  {k!r}: NOT IN out.twb")
    elif o == nb[k]:
        same += 1
    else:
        print(f"  {k!r}: DIFFERS  out={len(o)} prod={len(nb[k])}")
print(f"  ({same} of {len(lp)} byte-identical)")

print("\n=== Landing Page dashboard ===")
dn, do = dash_block(new, "Landing Page"), dash_block(out, "Landing Page")
print(f"  prod present={dn is not None} out present={do is not None}")
if dn and do:
    print(f"  identical={dn == do}  out={len(do)} prod={len(dn)}")

print("\n=== windows: which are hidden in prod ===")
for m in re.finditer(r"<window class='(worksheet|dashboard)'([^>]*)>", new):
    attrs = m.group(2)
    nm = re.search(r"name='([^']*)'", attrs)
    if nm and (nm.group(1).startswith("LP - ") or nm.group(1) == "Landing Page"):
        print(
            f"  {nm.group(1)!r}: hidden={"hidden='true'" in attrs} maximized={"maximized='true'" in attrs}"
        )

print("\n=== maximized window in prod (the default view) ===")
for m in re.finditer(r"<window[^>]*maximized='true'[^>]*>", new):
    print(" ", m.group(0)[:160])

print("\n=== Calculation_77 sites in prod ===")
for m in re.finditer(r"name='\[(Calculation_77\d+)\]'[^>]*", new):
    print(" ", m.group(0)[:120])
