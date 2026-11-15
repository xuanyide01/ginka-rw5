from pathlib import Path
import io
import json
import zipfile
from PIL import Image
from fontTools.ttLib import TTFont
from rpk_signature import audit

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "src/manifest.json").read_text("utf-8"))
rpk_path = ROOT / "dist" / f'{manifest["package"]}.debug.{manifest["versionName"]}.rpk'

report = audit(rpk_path)
assert report["bytes"] < 25000000, report["bytes"]
assert report["entries"] <= 4100, report["entries"]

z = zipfile.ZipFile(rpk_path)
assert json.loads(z.read("manifest-watch.json")) == manifest
assert manifest["package"] == "com.antigravity.ginka.rw5"
assert manifest["config"]["designWidth"] == 432

images = 0
audio_or_video = []
for name in z.namelist():
    if name.endswith("/"):
        continue
    low = name.lower()
    if low.endswith((".mp3", ".ogg", ".opus", ".wav", ".m4a", ".mp4", ".wmv", ".avi", ".webm")):
        audio_or_video.append(name)
    if name.startswith("common/"):
        assert z.read(name) == (ROOT / "src" / name).read_bytes(), name
    if low.endswith((".png", ".jpg", ".jpeg")):
        im = Image.open(io.BytesIO(z.read(name)))
        im.load()
        images += 1
        assert im.width <= 432 and im.height <= 286, (name, im.size)

assert not audio_or_video, audio_or_video

icon = Image.open(io.BytesIO(z.read("common/logo.png")))
assert icon.size == (192, 192) and icon.mode == "RGBA"
assert all(icon.getpixel(q)[3] == 0 for q in [(0, 0), (191, 0), (0, 191), (191, 191)])

font_cmap = TTFont(io.BytesIO(z.read("common/ginka-text.otf"))).getBestCmap()
strings = []


def visit(v):
    if isinstance(v, str):
        strings.append(v)
    elif isinstance(v, list):
        for x in v:
            visit(x)
    elif isinstance(v, dict):
        for x in v.values():
            visit(x)


for n in z.namelist():
    if n.startswith("common/") and n.endswith(".txt"):
        visit(json.loads(z.read(n)))
for s in strings:
    assert all(c.isspace() or ord(c) < 32 or ord(c) in font_cmap or c == "\ufeff" for c in s), repr(s)

gallery = json.loads(z.read("common/gallery.txt"))
report.update(
    commonFilesMatchSource=True,
    decodedImages=images,
    fontCoverageStrings=len(strings),
    circularIcon=True,
    galleryGroups=len(gallery),
    galleryImages=sum(len(g["variants"]) for g in gallery),
    audioOrVideoEntries=0,
    physicalDeviceTested=False,
)
(ROOT / "reports/package-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
print(json.dumps(report, ensure_ascii=False))
