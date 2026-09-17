"""crop_lp.py: crop the landing render into the regions to read."""

from pathlib import Path

# trunk-ignore(pyright/reportMissingImports): pillow is a `uv run --with` one-off dep
from PIL import Image

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
img = Image.open(LP / "render-landing-page.png")
W, H = img.size
sx, sy = W / 1366, H / 1500
BOXES = {
    "header": (0, 0, 1366, 96),
    "tiles": (0, 88, 1366, 316),
    "strip": (0, 308, 1366, 486),
    "cards": (0, 478, 1366, 716),
    "definitions": (0, 708, 1366, 1116),
    "coverage": (0, 1108, 1366, 1336),
    "links": (0, 1328, 1366, 1500),
}
for name, (x0, y0, x1, y1) in BOXES.items():
    img.crop((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))).save(
        LP / f"crop-{name}.png"
    )
    print("wrote", name)
