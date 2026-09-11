"""Build probe.twbx: final.twbx with the 13 compared sheets unhidden.

The REST publish does NOT override `hidden='true'` in `<windows>` -- a window
marked hidden is simply not a publishable view, and `hidden_views` can only
hide more, never reveal. So the probe package has to unhide them in the XML.
"""

import shutil
import zipfile
from pathlib import Path

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
SRC = LP / "final.twbx"
DST = LP / "probe.twbx"

UNHIDE = [
    "LP - Tile Y1 GPA",
    "LP - Tile Course Failures",
    "LP - Tile Cumulative GPA",
    "LP - Tile Gradebook Health",
    "LP - Strip Y1 GPA",
    "LP - Strip Course Failures",
    "LP - Strip Cumulative GPA",
    "LP - Strip Gradebook Health",
    "Y1 Landing - BAN Network ≥3.0",
    "Y1 Landing - BAN Network Failing ≥2",
    "GPA - BAN % 3.0+",
    "GPA - BAN Students needed",
    "BAN Network",
]

with zipfile.ZipFile(SRC) as z:
    twb_name = next(n for n in z.namelist() if n.endswith(".twb"))
    twb = z.read(twb_name)

before = twb.count(b"hidden='true'")
for name in UNHIDE:
    esc = name.replace("&", "&amp;").replace("<", "&lt;")
    needle = b"<window class='worksheet' hidden='true'"
    # Find the exact window element for this name and drop just its hidden attr.
    tag = f"name='{esc}'".encode()
    idx = 0
    hits = 0
    while True:
        i = twb.find(needle, idx)
        if i == -1:
            break
        end = twb.find(b">", i)
        if tag in twb[i:end]:
            twb = twb[:i] + twb[i:end].replace(b" hidden='true'", b"", 1) + twb[end:]
            hits += 1
            idx = i
        else:
            idx = end
    if hits != 1:
        raise RuntimeError(f"{name!r}: expected 1 hidden window, matched {hits}")

after = twb.count(b"hidden='true'")
print(f"hidden='true' windows: {before} -> {after} (removed {before - after})")
if before - after != len(UNHIDE):
    raise RuntimeError("wrong number of windows unhidden")

shutil.copy2(SRC, DST)
# zipfile cannot replace an entry in place; rebuild the archive.
tmp = LP / "probe-tmp.twbx"
with (
    zipfile.ZipFile(SRC) as zin,
    zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout,
):
    for info in zin.infolist():
        data = twb if info.filename == twb_name else zin.read(info.filename)
        zout.writestr(info, data)
tmp.replace(DST)
print(f"probe.twbx: {DST.stat().st_size / 1e6:.1f} MB; twb entry {twb_name}")

with zipfile.ZipFile(DST) as z:
    check = z.read(twb_name)
if check != twb:
    raise RuntimeError("packaged .twb does not match the edited bytes")
print("packaged .twb byte-identical to the edited source")
