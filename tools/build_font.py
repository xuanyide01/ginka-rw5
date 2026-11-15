"""Build GINKA Watch 5 text font subset from extracted SourceHanSansSC-Regular.otf."""
from pathlib import Path
import json
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(r"E:\Antigravity\ginka-rw5")
COMMON = ROOT / "src" / "common"
REPORTS = ROOT / "reports"
UI_FILE = ROOT / "src" / "pages" / "index" / "index.ux"


def collect_text_chars(chars: set):
    for p in sorted((COMMON / "story").rglob("*.txt")):
        for item in json.loads(p.read_text("utf-8")):
            chars.update(item.get("s") or "")
            chars.update(item.get("t") or "")
    graph = json.loads((ROOT / "converted" / "graph.json").read_text("utf-8"))
    for n in graph["nodes"].values():
        chars.update(n.get("title") or "")
        for c in n.get("choices") or []:
            chars.update(c.get("text") or "")
    for ch in graph.get("chapters") or []:
        chars.update(ch.get("title") or "")
    gal = COMMON / "gallery.txt"
    if gal.exists():
        chars.update(gal.read_text("utf-8"))
    if UI_FILE.exists():
        chars.update(UI_FILE.read_text("utf-8"))
    chars.update("".join(chr(c) for c in range(0x20, 0x7F)))
    chars.update("…—～·「」『』【】（）《》、。！？：；“”‘’")


def main():
    ui_meta = json.loads((REPORTS / "ui-font-extracts.json").read_text("utf-8"))
    source = Path(ui_meta["font"]["output"])
    assert source.exists(), source

    chars = set()
    collect_text_chars(chars)
    chars.discard("\ufeff")

    font = TTFont(source)
    cmap = font.getBestCmap()
    missing = sorted(c for c in chars if not c.isspace() and ord(c) >= 32 and ord(c) not in cmap)
    if missing:
        raise RuntimeError(f"Missing glyphs in source font ({len(missing)}): {''.join(missing[:40])!r}")

    coverage = {ord(c) for c in chars if ord(c) in cmap and (not c.isspace() or ord(c) == 0x20)}
    coverage.add(0x20)

    options = subset.Options()
    options.layout_features = []
    options.drop_tables += ["BASE", "GSUB", "GPOS", "VORG", "vhea", "vmtx"]
    options.desubroutinize = True
    options.hinting = False
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=coverage)
    subsetter.subset(font)

    for name in font["name"].names:
        if name.nameID in (1, 3, 4, 6, 16):
            name.string = "GinkaWatchText".encode(name.getEncoding(), errors="replace")
    if "CFF " in font:
        font["CFF "].cff.fontNames = ["GinkaWatchText"]

    output = COMMON / "ginka-text.otf"
    font.save(output)
    out_cmap = set(TTFont(output).getBestCmap())
    assert coverage.issubset(out_cmap), "Subset missing requested codepoints!"

    report = {
        "font": "GinkaWatchText",
        "source": str(source),
        "codepoints": len(coverage),
        "glyphs": len(font.getGlyphOrder()),
        "fontBytes": output.stat().st_size,
        "desubroutinize": True,
        "hinting": False,
        "allTextCovered": True,
        "license": "SIL OFL 1.1",
    }
    (REPORTS / "text-font.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
