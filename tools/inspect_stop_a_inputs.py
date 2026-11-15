"""Inspect Stop A inputs: PSB cut-in layers (02156/02162/02181 etc.), imagediffmap, envinit lay_black/white, ghost stands, and GINKA UI assets."""
import sys
import json
import hashlib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AG_ROOT = Path(r"E:\Antigravity")
PROBE = AG_ROOT / "probe"
REPORTS0 = AG_ROOT / "reports" / "phase0"
CODEX_GINKA = Path(r"D:\codex\2026-10-30\ginka-rw5")


def file_hash(name: str) -> str:
    n = name.replace("\\", "/").split("/")[-1]
    n = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in n)
    return hashlib.blake2s((n + "xp3hnp").encode("utf-16le")).hexdigest()


def main():
    probed = {}
    for p in sorted(REPORTS0.glob("*.probed_entries.json")):
        arc = p.name.removesuffix(".xp3.probed_entries.json")
        probed[arc] = json.loads(p.read_text(encoding="utf-8-sig"))

    # 1. Check cr_data entries around 2150..2195 and all PSB/SimpleCrypt in cr_data, data, bgimage
    print("=== 1. cr_data 2150..2195 ===")
    for e in probed["cr_data"]:
        if 2150 <= e["index"] <= 2195:
            print(e["index"], e["kind"], e["original"], e.get("fileHash", "")[:16], e.get("extractedFile"))

    # Search all decoded PSB JSONs and text files for ci030al, ci031al, ci023b2l, ci004bl
    targets = ("ci030al", "ci031al", "ci023b2l", "ci004bl", "ci030a", "ci031a", "ci023b2", "ci004b")
    print("\n=== 2. Search decoded PSB & text for ci030al / ci031al / ci023b2l / ci004bl ===")
    for folder in (PROBE / "decoded" / "psb", PROBE / "decoded" / "text"):
        for f in sorted(folder.rglob("*")):
            if not f.is_file():
                continue
            txt = f.read_text(encoding="utf-8", errors="replace")
            low = txt.lower()
            hits = [t for t in targets if t in low]
            if hits:
                # Avoid scenario scripts unless needed; show non-scenario or summarize
                print(f"HIT {hits} in {f.relative_to(PROBE)} ({len(txt)} chars)")

    # 3. Check imagediffmap / imagenamemap / envinit for lay_black, lay_white, diff rules
    print("\n=== 3. Search decoded/text for lay_black, lay_white, imagediffmap ===")
    for f in sorted((PROBE / "decoded" / "text").rglob("*.txt")):
        txt = f.read_text(encoding="utf-8", errors="replace")
        low = txt.lower()
        if "lay_black" in low or "lay_white" in low or "imagediff" in low or "ev101" in low:
            print(f"TEXT HIT in {f.relative_to(PROBE)}:")
            for i, line in enumerate(txt.splitlines(), 1):
                ll = line.lower()
                if any(k in ll for k in ("lay_black", "lay_white", "diff", "ci030", "ci031", "ci023", "ci004")):
                    print(f"  L{i}: {line[:160]}")

    # 4. Check ghost stands: 呪いＡ.stand, 呪いＢ.stand, 呪いＣ.stand
    print("\n=== 4. Ghost stands ===")
    for gs in ("呪いＡ.stand", "呪いＢ.stand", "呪いＣ.stand"):
        fh = file_hash(gs)
        for arc in ("patch_cr_data", "cr_data"):
            for e in probed[arc]:
                if e.get("fileHash") == fh:
                    tf = PROBE / "decoded" / "text" / arc / Path(e["extractedFile"]).name
                    st_txt = tf.read_text(encoding="utf-8")
                    print(f"{gs} ({arc} #{e['index']}): {st_txt.strip()}")
                    # Also find its .sinfo
                    for line in st_txt.splitlines():
                        if "filename" in line:
                            print("  ->", line.strip())

    for sbase in ("tnor01", "tnor02", "tnor03", "tcur01", "tcur02", "tcur03"):
        fh = file_hash(sbase + ".sinfo")
        for arc in ("patch_cr_data", "cr_data"):
            for e in probed[arc]:
                if e.get("fileHash") == fh:
                    tf = PROBE / "decoded" / "text" / arc / Path(e["extractedFile"]).name
                    print(f"SINFO {sbase}.sinfo:\n{tf.read_text(encoding='utf-8')}")

    # 5. Inspect UI assets in data.xp3 and patch.xp3:
    # - data PSB files (503, 506)
    # - uipsd TJS_NS0 (.pbd.json) packbase / names / packlist
    # - uipsd TLG5 files
    # - OTF / TTF / TFT_FONT files in data.xp3
    print("\n=== 5. GINKA UI Assets (Title PSB, uipsd NS0 + TLG5, Fonts) ===")
    for p in sorted((PROBE / "decoded" / "psb" / "data").glob("*.json")):
        obj = json.loads(p.read_text(encoding="utf-8"))
        print("DATA PSB:", p.name, "keys:", list(obj.keys())[:20])
        # Also print accompanying text/asd around 500..510 in data
    for e in probed["data"]:
        if 498 <= e["index"] <= 512:
            print("DATA image/ entry:", e["index"], e["kind"], e["original"], e.get("width"), e.get("height"), e.get("fileHash", "")[:16])
            if e.get("extractedFile") and e["kind"] == "SimpleCrypt":
                tf = PROBE / "decoded" / "text" / "data" / Path(e["extractedFile"]).name
                if tf.exists():
                    print("  ASD/TXT:", tf.read_text(encoding="utf-8")[:400])

    print("\n--- uipsd NS0 dictionaries (data & patch) ---")
    for arc in ("patch", "data"):
        s0_dir = PROBE / "decoded" / "s0" / arc
        if not s0_dir.exists():
            continue
        items = []
        for jf in sorted(s0_dir.glob("*.pbd.json")):
            d = json.loads(jf.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                pb = d.get("packbase")
                pl = d.get("packlist")
                nms = list(d.get("names", {}).keys())[:8] if isinstance(d.get("names"), dict) else d.get("names")
                items.append((jf.name, pb, len(pl) if isinstance(pl, list) else None, nms))
        print(f"{arc} NS0 count={len(items)}:")
        for row in items:
            print(" ", row)

    print("\n--- Fonts in data.xp3 ---")
    # Also check embfontlist.tjs and deffontmap.tjs!
    for fname in ("embfontlist.tjs", "deffontmap.tjs", "uidef.tjs", "custom.tjs", "default.tjs"):
        fh = file_hash(fname)
        for arc in ("patch", "data"):
            for e in probed[arc]:
                if e.get("fileHash") == fh:
                    tf = PROBE / "decoded" / "text" / arc / Path(e["extractedFile"]).name
                    if tf.exists():
                        print(f"FONT/UI CONFIG {fname} ({arc} #{e['index']}):")
                        print(tf.read_text(encoding="utf-8")[:1200])
                    break


if __name__ == "__main__":
    main()
