"""Deep inspect:
1. Exact occurrences of ci030al / ci031al / ci023b2l / ci004bl / cg_ci* in 02156/02162/02181 (and patch_cr_data 04369/04375/04394)
2. Full text of imagediffmap (data #543 and any other diff/map files) and envinit.tjs L2025..2070
3. Full text of tnoa01.sinfo, tnob01.sinfo, tnoc01.sinfo
4. Exact filenames in probe/decoded/s0/ (NS0 UI dictionaries) + TLG5 UI atlases + OTF/TTF fonts
5. Check all unmatched entries in bgimage/cut, bgimage2, cr_event, cr_data, data!
"""
import sys
import json
import hashlib
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AG_ROOT = Path(r"E:\Antigravity")
PROBE = AG_ROOT / "probe"
REPORTS0 = AG_ROOT / "reports" / "phase0"


def file_hash(name: str) -> str:
    n = name.replace("\\", "/").split("/")[-1]
    n = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in n)
    return hashlib.blake2s((n + "xp3hnp").encode("utf-16le")).hexdigest()


def main():
    probed = {
        p.name.removesuffix(".xp3.probed_entries.json"): json.loads(p.read_text(encoding="utf-8-sig"))
        for p in sorted(REPORTS0.glob("*.probed_entries.json"))
    }

    # 1. Inspect 02156, 02162, 02181 and 04369, 04375, 04394 around ci030/ci031/ci023/ci004
    print("=== 1. PSB context around ci030al / ci031al / ci023b2l / ci004bl ===")
    for rel in (
        "psb/cr_data/02156__94d4a97c61498621__fc6dd471c3c04022.json",
        "psb/cr_data/02162__94d4a97c61498621__b01056daaa3bfd91.json",
        "psb/cr_data/02181__94d4a97c61498621__34c62707a927467d.json",
    ):
        p = PROBE / "decoded" / rel
        obj = json.loads(p.read_text(encoding="utf-8"))
        print(f"\n--- {rel} (name={obj.get('name')}, topKeys={list(obj.keys())}) ---")
        raw = p.read_text(encoding="utf-8")
        for m in re.finditer(r'.{0,120}(?:ci030|ci031|ci023b2|ci004b).{0,120}', raw, re.I):
            s = m.group(0).replace("\r", "").replace("\n", " ")
            print("  MATCH:", s[:240])

    # 2. Full imagediffmap (data #543) & envinit.tjs L2020..2080 & search all text files for imagediffmap / diff / stage / event / cut
    print("\n=== 2. data #543 (imagediffmap.txt) ===")
    p543 = PROBE / "decoded/text/data/00543__f051058efed71c42__be34d0aedc33f5df.txt"
    print(p543.read_text(encoding="utf-8"))

    print("=== 2b. Check all unmatched SimpleCrypt in cr_data, patch, patch_cr_data, data/main ===")
    for arc in ("cr_data", "patch_cr_data", "patch", "data"):
        tdir = PROBE / "decoded/text" / arc
        for tf in sorted(tdir.glob("*.txt")):
            idx = int(tf.name.split("__")[0])
            if (arc == "cr_data" and idx in (1, 3, 4, 5, 6, 2192, 2193, 2194)) or \
               (arc == "patch_cr_data" and idx <= 10) or \
               (arc == "patch" and idx >= 70) or \
               (arc == "data" and 520 <= idx <= 560):
                content = tf.read_text(encoding="utf-8", errors="replace")
                first_lines = " | ".join(content.splitlines()[:4])
                print(f"  {arc} #{idx:05d} ({len(content)} chars): {first_lines[:180]}")

    print("\n=== 2c. envinit.tjs around lay_white / lay_black & stage / event definitions ===")
    p533 = PROBE / "decoded/text/data/00533__f051058efed71c42__1028c8cc9ff94683.txt"
    lines533 = p533.read_text(encoding="utf-8").splitlines()
    for i in range(max(0, 2020), min(len(lines533), 2080)):
        print(f"  L{i+1}: {lines533[i]}")
    # Also search envinit.tjs and all tjs2 string pools for imagediffmap or diff!
    for i, line in enumerate(lines533, 1):
        if any(k in line.lower() for k in ("imagediff", "imagenamemap", "ci0", "cut", "altstorage")):
            print(f"  envinit L{i}: {line[:160]}")

    # Check base.stage in bgimage!
    print("\n=== 2d. bgimage SimpleCrypt non-asd files (e.g. base.stage) ===")
    for tf in sorted((PROBE / "decoded/text/bgimage").glob("*.txt")):
        txt = tf.read_text(encoding="utf-8", errors="replace")
        if not txt.lstrip().startswith(";!") and "@clip" not in txt:
            print(f"  bgimage {tf.name} ({len(txt)} chars):")
            print(txt[:1500])

    # 3. Ghost stands sinfo: tnoa01, tnob01, tnoc01
    print("\n=== 3. Ghost stands sinfo: tnoa01, tnob01, tnoc01 ===")
    for sbase in ("tnoa01", "tnob01", "tnoc01"):
        fh = file_hash(sbase + ".sinfo")
        for arc in ("patch_cr_data", "cr_data"):
            for e in probed[arc]:
                if e.get("fileHash") == fh:
                    tf = PROBE / "decoded/text" / arc / Path(e["extractedFile"]).name
                    print(f"--- {sbase}.sinfo ({arc} #{e['index']}) ---")
                    print(tf.read_text(encoding="utf-8"))

    # 4. Inspect probe/decoded/s0/ actual filenames + UI NS0 + TLG5 + Fonts!
    print("\n=== 4. probe/decoded/s0 actual files (NS0 UI dictionaries) ===")
    for arc in ("patch", "data"):
        s0_dir = PROBE / "decoded/s0" / arc
        if s0_dir.exists():
            files = sorted(s0_dir.iterdir())
            print(f"{arc} s0 files count={len(files)}, sample names={[f.name for f in files[:5]]}")
            for jf in files:
                d = json.loads(jf.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    pb = d.get("packbase")
                    pl = d.get("packlist")
                    nms = list(d.get("names", {}).keys())[:6] if isinstance(d.get("names"), dict) else None
                    print(f"  {jf.name[:28]} -> packbase={pb!r}, packlist={pl}, names_sample={nms}")

    print("\n=== 5. Full embfontlist.tjs (patch #81) ===")
    p81 = PROBE / "decoded/text/patch/00081__94d4a97c61498621__4396cc08cb217a14.txt"
    if not p81.exists():
        # find by hash
        fh = file_hash("embfontlist.tjs")
        for e in probed["patch"]:
            if e.get("fileHash") == fh:
                p81 = PROBE / "decoded/text/patch" / Path(e["extractedFile"]).name
    print(p81.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
