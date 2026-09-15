import re
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
t = src.read_text(encoding="utf-8", newline="")
for m in re.finditer(r"<worksheet name='([^']*)'>.*?</worksheet>", t, re.S):
    if m.group(1).startswith("LP - "):
        slug = re.sub(r"[^A-Za-z0-9]+", "_", m.group(1)).strip("_")
        (out / f"{slug}.xml").write_text(
            m.group(0).replace("\r\n", "\n"), encoding="utf-8"
        )
m = re.search(r"<dashboard[^>]*name='Landing Page'.*?</dashboard>", t, re.S)
if m:
    (out / "_dashboard.xml").write_text(
        m.group(0).replace("\r\n", "\n"), encoding="utf-8"
    )
