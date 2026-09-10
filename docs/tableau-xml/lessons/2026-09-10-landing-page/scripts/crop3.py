from pathlib import Path

from PIL import Image

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
src = Image.open(LP / "render-landing-page.png").convert("RGB")
sx, sy = src.size[0] / 1366, src.size[1] / 1500
BOXES = {
    "hdr": (0, 0, 1366, 92),
    "tiles": (0, 88, 1366, 300),
    "strip": (0, 292, 1366, 452),
}
for name, (x0, y0, x1, y1) in BOXES.items():
    im = src.crop((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)))
    im = im.resize((1000, max(1, int(im.height * 1000 / im.width))), Image.LANCZOS)
    p = LP / f"c3-{name}.jpg"
    im.save(p, "JPEG", quality=72)
    print(f"{p.name}: {im.width}x{im.height} {p.stat().st_size}")
