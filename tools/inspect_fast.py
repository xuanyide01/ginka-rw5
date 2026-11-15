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
from ginka_sources import file_hash

diag = json.loads((PHASE0 / "unmatched_diagnostic.json").read_text(encoding="utf-8"))
print("=== 1. unmatched_diagnostic.json keys & bgimage / bgimage2 / cr_event unmatched ===")
print("keys:", list(diag.keys()))
for k, v in diag.items():
    if isinstance(v, dict):
        print(f"  {k}: { {kk: (len(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()} }")
        if k in ("bgimage.xp3", "bgimage2.xp3", "cr_event.xp3", "by_archive"):
            print("   detail:", json.dumps(v, ensure_ascii=False)[:1500])

tables = json.loads((PHASE0 / "hxv4_decrypted_tables.json").read_text(encoding="utf-8"))
print("\n=== 2. Check hxv4_decrypted_tables sample entry keys & all ci030/ci031/ci023/ci004 matches ===")
sample_arc = next(iter(tables))
print("sample entry:", tables[sample_arc][0])

for arc, items in tables.items():
    probed = json.loads((PHASE0 / f"{arc}.probed_entries.json").read_text(encoding="utf-8"))
    for it in items:
        mn = (it.get("matched_name") or it.get("name") or "")
        if any(x in mn.lower() for x in ("ci030", "ci031", "ci023", "ci004", "imagediff")):
            idx = it.get("index", -1)
            pr = probed[idx] if 0 <= idx < len(probed) else {}
            print(f"  {arc} idx={idx}: matched={mn!r} dir={it.get('matched_dir')!r} fh={it.get('file_hash')[:16]} size={pr.get('original')} kind={pr.get('kind')} w={pr.get('width')} h={pr.get('height')}")

print("\n=== 3. Exact unmatched entries in bgimage.xp3 & bgimage2.xp3 ===")
unmatched_fh = {}
for arc in ["bgimage.xp3", "bgimage2.xp3", "cr_event.xp3"]:
    probed = json.loads((PHASE0 / f"{arc}.probed_entries.json").read_text(encoding="utf-8"))
    for idx, it in enumerate(tables[arc]):
        pr = probed[idx]
        if not it.get("matched_name") and not pr.get("isGarbage"):
            unmatched_fh[it["file_hash"]] = (arc, idx, it.get("matched_dir"), pr.get("original"), pr.get("kind"), pr.get("width"), pr.get("height"))
            print(f"  UNMATCHED {arc} #{idx}: dir={it.get('matched_dir')} fh={it['file_hash'][:16]} size={pr.get('original')} kind={pr.get('kind')} {pr.get('width')}x{pr.get('height')}")

print("\n=== 4. Inspect exact PSB lines in 02156 / 02162 / 02181 (and patch_cr_data 04369 / 04375 / 04394) ===")
for arc_sub, prefix in [("cr_data", "02156"), ("cr_data", "02162"), ("cr_data", "02181"), ("patch_cr_data", "04369"), ("patch_cr_data", "04375"), ("patch_cr_data", "04394")]:
    for p in (PSB_DIR / arc_sub).glob(f"{prefix}*.json"):
        obj = json.loads(p.read_text(encoding="utf-8"))
        scn = obj["scenes"][0]
        print(f"\n  PSB {arc_sub}/{p.name} name={obj.get('name')}:")
        for li, ln in enumerate(scn.get("lines", [])):
            s = json.dumps(ln, ensure_ascii=False)
            if any(k in s for k in ["ci030al", "ci031al", "ci023b2l", "ci004bl"]):
                # print surrounding lines too
                for ctx in range(max(0, li - 3), min(len(scn["lines"]), li + 4)):
                    print(f"    line[{ctx}]: {json.dumps(scn['lines'][ctx], ensure_ascii=False)[:240]}")
                break

print("\n=== 5. Search TJS scripts in data/patch for imagediffmap.txt / resmap.txt / PIMG / PSB diff resolution ===")
for p in sorted(TEXT_DIR.rglob("*.txt")):
    txt = p.read_text(encoding="utf-8", errors="replace")
    if any(k in txt for k in ["imagediffmap", "resmap", "EV101AA"]):
        print(f"  TJS/TXT HIT {p.relative_to(TEXT_DIR)}:")
        for ln_no, ln in enumerate(txt.splitlines(), 1):
            if any(k in ln for k in ["imagediff", "resmap", "diff", "EV101", "PIMG", "psb", "parse"]):
                print(f"    L{ln_no}: {ln[:160]}")

print("\n=== 6. Compact summary of ALL NS0 UI layout dictionaries in data & patch ===")
for arc in ["data", "patch"]:
    arc_dir = S0_DIR / arc
    t_items = tables[f"{arc}.xp3"]
    probed = json.loads((PHASE0 / f"{arc}.xp3.probed_entries.json").read_text(encoding="utf-8"))
    pack_summary = {}
    for p in sorted(arc_dir.glob("*.ns0.json")):
        idx = int(p.name.split("__")[0])
        obj = json.loads(p.read_text(encoding="utf-8"))
        pb = tuple(obj.get("packbase", [])) if isinstance(obj, dict) else ()
        names = list(obj.get("names", {}).keys())[:6] if isinstance(obj, dict) and isinstance(obj.get("names"), dict) else None
        order_len = len(obj.get("order", [])) if isinstance(obj, dict) and isinstance(obj.get("order"), list) else None
        it = t_items[idx]
        pack_summary.setdefault(pb, []).append((idx, it["file_hash"][:16], it.get("matched_name"), names, order_len))
    print(f"\n  [{arc}] distinct packbase groups = {len(pack_summary)}:")
    for pb, items in sorted(pack_summary.items()):
        print(f"    packbase={list(pb)}: {len(items)} files -> sample={items[:2]}")
