import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"E:\Antigravity")
PHASE0 = ROOT / "reports" / "phase0"
S0_DIR = ROOT / "probe" / "decoded" / "s0"
TEXT_DIR = ROOT / "probe" / "decoded" / "text"
PSB_DIR = ROOT / "probe" / "decoded" / "psb"

sys.path.insert(0, r"D:\codex\2026-10-30\ginka-rw5\tools")
from ginka_sources import Sources, file_hash

src = Sources()

print("=== 1. Test *_1.csv / *_1.txt and all control file names ===")
bases = ["imagediffmap", "imagenamemap", "imageconvmap", "resmap", "multires", "cglist", "scnlist", "charinit", "soundlist", "bgmlist", "cutin"]
for b in bases:
    for suf in ["", "_1", "_2", "_append", "_patch"]:
        for ext in [".csv", ".txt", ".tjs"]:
            nm = f"{b}{suf}{ext}"
            hit = src.find(nm, required=False)
            if hit:
                print(f"  FOUND {nm!r} -> {hit['archive']} #{hit['index']} size={hit['original']} fh={hit['fileHash'][:16]}")

print("\n=== 2. List ALL decoded text files in cr_data, patch_cr_data, patch, bgimage ===")
for arc in ["patch_cr_data", "cr_data", "patch", "bgimage"]:
    files = sorted((TEXT_DIR / arc).glob("*")) if (TEXT_DIR / arc).exists() else []
    print(f"  {arc}: {len(files)} decoded text files")
    for p in files[:40]:
        first_line = p.read_text(encoding="utf-8", errors="replace").splitlines()[:2]
        print(f"    {p.name} ({p.stat().st_size} B): {first_line}")

print("\n=== 3. Check ALL matched files in bgimage2.xp3 and bgimage.xp3 cut/ ===")
diag = json.loads((PHASE0 / "unmatched_diagnostic.json").read_text(encoding="utf-8"))
print("  bgimage cut/::PNG unmatched:", json.dumps(diag["bgimage.xp3"].get("cut/::PNG"), ensure_ascii=False))
print("  bgimage ::PNG unmatched:", json.dumps(diag["bgimage.xp3"].get("::PNG"), ensure_ascii=False))
print("  bgimage bg2/::PNG unmatched:", json.dumps(diag["bgimage.xp3"].get("bg2/::PNG"), ensure_ascii=False))
print("  bgimage2 ::PNG unmatched:", json.dumps(diag["bgimage2.xp3"].get("::PNG"), ensure_ascii=False))

# Check what WAS matched in bgimage2.xp3 and bgimage.xp3!
probed_bg2 = json.loads((PHASE0 / "bgimage2.xp3.probed_entries.json").read_text(encoding="utf-8"))
print("\n  Sample matched in bgimage2.xp3:")
for e in probed_bg2[:25]:
    print(f"    bgimage2 #{e['index']}: matched={e.get('matchedName')} fh={(e.get('fileHash') or '')[:16]} {e.get('width')}x{e.get('height')} size={e.get('original')}")

probed_bg1 = json.loads((PHASE0 / "bgimage.xp3.probed_entries.json").read_text(encoding="utf-8"))
print("\n  Sample entries in bgimage.xp3 around ci030 / ci031 / ci023 / ci004:")
for name in ["ci030a.png", "ci031a.png", "ci023b.png", "ci023b2.png", "ci004a.png", "ci004b.png"]:
    hit = src.find(name, required=False)
    print(f"    find({name!r}) -> { {k: hit.get(k) for k in ('archive', 'index', 'fileHash', 'original', 'width', 'height', 'pathHash')} if hit else None }")

print("\n=== 4. Inspect FULL line[146] of scn001.ks (02156) and corresponding lines in scn007.ks (02162) & scn108.ks (02181) ===")
for arc_sub, prefix in [("cr_data", "02156"), ("cr_data", "02162"), ("cr_data", "02181")]:
    for p in (PSB_DIR / arc_sub).glob(f"{prefix}*.json"):
        obj = json.loads(p.read_text(encoding="utf-8"))
        if "scenes" not in obj:
            continue
        scn = obj["scenes"][0]
        print(f"\n  PSB {arc_sub}/{p.name} name={obj.get('name')}:")
        for li, ln in enumerate(scn.get("lines", [])):
            s = json.dumps(ln, ensure_ascii=False)
            for kw in ["ci030al", "ci031al", "ci023b2l", "ci004bl"]:
                if kw in s:
                    print(f"    HIT {kw} at line[{li}]:")
                    for ctx in range(max(0, li - 4), min(len(scn["lines"]), li + 5)):
                        print(f"      line[{ctx}]: {json.dumps(scn['lines'][ctx], ensure_ascii=False)}")

print("\n=== 5. Check TJS2100 / TJS engine code in data for imagediffmap parsing ===")
# Check decoded text files in data for 'imagediffmap'
for p in sorted((TEXT_DIR / "data").glob("*.txt")):
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "imagediffmap" in txt or "resmap" in txt or "imageconvmap" in txt or "imagenamemap" in txt:
        print(f"  ENGINE FILE {p.name}:")
        for ln_no, ln in enumerate(txt.splitlines(), 1):
            if any(w in ln for w in ["imagediffmap", "resmap", "imageconvmap", "imagenamemap", "diff", "split"]):
                print(f"    L{ln_no}: {ln[:160]}")

print("\n=== 6. Compact summary of ALL NS0 UI layout dictionaries in data & patch ===")
for arc in ["data", "patch"]:
    arc_dir = S0_DIR / arc
    probed = {e["index"]: e for e in json.loads((PHASE0 / f"{arc}.xp3.probed_entries.json").read_text(encoding="utf-8"))}
    pack_summary = {}
    for p in sorted(arc_dir.glob("*.ns0.json")):
        idx = int(p.name.split("__")[0])
        obj = json.loads(p.read_text(encoding="utf-8"))
        pb = tuple(obj.get("packbase", [])) if isinstance(obj, dict) else ()
        names = list(obj.get("names", {}).keys())[:6] if isinstance(obj, dict) and isinstance(obj.get("names"), dict) else None
        order_len = len(obj.get("order", [])) if isinstance(obj, dict) and isinstance(obj.get("order"), list) else None
        pr = probed.get(idx, {})
        pack_summary.setdefault(pb, []).append((idx, pr.get("fileHash", "")[:16], names, order_len))
    print(f"\n  [{arc}] distinct packbase groups = {len(pack_summary)}:")
    for pb, items in sorted(pack_summary.items()):
        print(f"    packbase={list(pb)}: {len(items)} files -> sample={items[:2]}")
