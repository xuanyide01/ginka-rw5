import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"E:\Antigravity")
S0_DIR = ROOT / "probe" / "decoded" / "s0"
PSB_JSON_DIR = ROOT / "probe" / "decoded" / "psb"

sys.path.insert(0, r"D:\codex\2026-10-30\ginka-rw5\tools")
from ginka_sources import Sources, file_hash

src = Sources()

print("=== 1. Find imagediffmap.csv / resmap.csv / etc. via Sources.find ===")
for name in [
    "imagediffmap.csv", "imagediffmap.txt", "imagediff.csv", "diffmap.csv",
    "resmap.csv", "resmap.txt", "multires.csv", "multiresmap.csv",
    "cglist.csv", "cglist_1.csv", "charinit.csv", "envinit.tjs", "custom.tjs"
]:
    hit = src.find(name, required=False)
    print(f"  find({name!r}) -> { {k: hit[k] for k in ('archive', 'index', 'dirPath', 'fileHash', 'original') if k in hit} if hit else None }")

print("\n=== 2. Unmatched entries in bgimage, bgimage2, cr_event ===")
for arc in ["bgimage", "bgimage2", "cr_event"]:
    entries = src.entries[arc]
    unmatched = [e for e in entries if not e.get("matchedName") and not e.get("isGarbage")]
    print(f"  {arc}: total={len(entries)}, unmatched={len(unmatched)}")
    for e in unmatched:
        print(f"    idx={e['index']} dir={e.get('dirPath')} ph={e.get('pathHash')} fh={e.get('fileHash')} size={e.get('original')} magic={e.get('magic')} info={e.get('detail')}")

print("\n=== 3. Matched ci030 / ci031 / ci023 / ci004 entries across ALL archives ===")
for arc, entries in src.entries.items():
    for e in entries:
        mn = (e.get("matchedName") or "").lower()
        if any(mn.startswith(p) for p in ("ci030", "ci031", "ci023", "ci004")):
            print(f"  {arc} #{e['index']}: dir={e.get('dirPath')} mn={e.get('matchedName')} fh={e.get('fileHash')} size={e.get('original')} detail={e.get('detail')}")

print("\n=== 4. Search PSB files in probe/decoded/psb for ci030 / ci031 / ci023b2 / ci004b ===")
for p in sorted(PSB_JSON_DIR.rglob("*.json")):
    txt = p.read_text(encoding="utf-8", errors="replace")
    low = txt.lower()
    if any(kw in low for kw in ["ci030", "ci031", "ci023b2", "ci004b"]):
        obj = json.loads(txt)
        print(f"  PSB HIT in {p.relative_to(PSB_JSON_DIR)}: keys={list(obj.keys())[:10] if isinstance(obj, dict) else type(obj)}")
        def walk(node, path=""):
            if isinstance(node, dict):
                for k, v in node.items():
                    if any(kw in str(k).lower() or (isinstance(v, str) and kw in v.lower()) for kw in ["ci030", "ci031", "ci023b2", "ci004b"]):
                        print(f"    at {path}.{k} = {repr(v)[:200]}")
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    if isinstance(v, str) and any(kw in v.lower() for kw in ["ci030", "ci031", "ci023b2", "ci004b"]):
                        print(f"    at {path}[{i}] = {repr(v)[:200]}")
                    walk(v, f"{path}[{i}]")
        walk(obj)

print("\n=== 5. Sweep candidate names for the unmatched entries in bgimage & bgimage2 ===")
unmatched_hashes = {}
for arc in ["bgimage", "bgimage2", "cr_event"]:
    for e in src.entries[arc]:
        if not e.get("matchedName") and not e.get("isGarbage"):
            unmatched_hashes[e["fileHash"]] = (arc, e["index"], e.get("dirPath"), e.get("detail"))

cands = []
for prefix in ["ci", "bg", "ev", "sdcom", "cut", "cg", "mask", "rule", "eyecatch"]:
    for num in range(0, 400):
        for nfmt in [f"{num:02d}", f"{num:03d}"]:
            for v1 in ["", "a", "b", "c", "d", "e", "f", "g", "h"]:
                for v2 in ["", "1", "2", "3", "4", "_1", "_2"]:
                    for v3 in ["", "l", "_l", "ll", "_ll", "s", "_s", "_large", "_m"]:
                        for ext in [".png", ".tlg", ".jpg", ".psb", ".pimg", ".asd"]:
                            cands.append(f"{prefix}{nfmt}{v1}{v2}{v3}{ext}")
for c in cands:
    fh = file_hash(c)
    if fh in unmatched_hashes:
        print(f"  UNMATCHED HIT! {c!r} -> {fh}: {unmatched_hashes[fh]}")

print("\n=== 6. Compact summary of ALL NS0 UI layout dictionaries in data & patch ===")
for arc in ["data", "patch"]:
    arc_dir = S0_DIR / arc
    entries_by_idx = {e["index"]: e for e in src.entries[arc]}
    pack_summary = {}
    for p in sorted(arc_dir.glob("*.ns0.json")):
        idx = int(p.name.split("__")[0])
        obj = json.loads(p.read_text(encoding="utf-8"))
        pb = tuple(obj.get("packbase", [])) if isinstance(obj, dict) else ()
        names = list(obj.get("names", {}).keys())[:6] if isinstance(obj, dict) and isinstance(obj.get("names"), dict) else None
        order_len = len(obj.get("order", [])) if isinstance(obj, dict) and isinstance(obj.get("order"), list) else None
        ent = entries_by_idx.get(idx, {})
        pack_summary.setdefault(pb, []).append((idx, ent.get("fileHash"), ent.get("matchedName"), names, order_len))
    print(f"\n  [{arc}] distinct packbase groups = {len(pack_summary)}:")
    for pb, items in sorted(pack_summary.items()):
        print(f"    packbase={list(pb)}: {len(items)} files -> sample={items[:2]}")
