"""Plan all static images, composite CGs, _s portrait stacks, UI/font extractions, and Watch 5 asset budget."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import re

from tjs_data import loads

ROOT = Path(r"E:\Antigravity\ginka-rw5")
PHASE0_REPORTS = Path(r"E:\Antigravity\reports\phase0")
PROBE = Path(r"E:\Antigravity\probe")
CONV = ROOT / "converted"
REPORTS = ROOT / "reports"

# Search priority favors patch & standard HD (1280x720) over bgimage2 (2560x1440)
ARCHIVE_ORDER = ["patch_cr_data", "patch", "cr_data", "data", "bgimage", "cr_event", "bgimage2", "fgimage", "steam"]

# Verified fallback for 4 missing-HD cut-in *l references -> 1280x720 bases in bgimage.xp3
STATIC_FALLBACKS = {
    "ci004bl": "ci004b",
    "ci023b2l": "ci023b2",
    "ci030al": "ci030a",
    "ci031al": "ci031a",
}

# Verified synthetic solid layers from data/main/envinit.tjs
SOLID_MAP = {
    "lay_black": {"color": [0, 0, 0], "size": [1280, 720]},
    "lay_white": {"color": [255, 255, 255], "size": [1280, 720]},
}

# Verified empty-option ghost stands (tnoa01/b/c.sinfo each have only d1, p1, f1)
GHOST_DEFAULT_OPTIONS = {"dress": "d1", "pose": "p1", "face": "f1"}


def compact(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def file_hash(name: str) -> str:
    n = name.replace("\\", "/").split("/")[-1]
    # KiriKiri Hxv4 only lowercases ASCII A-Z (preserves fullwidth A-Z like Ａ/Ｂ/Ｃ/Ｄ)
    n = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in n)
    return hashlib.blake2s((n + "xp3hnp").encode("utf-16le")).hexdigest()


class ArchiveCatalog:
    def __init__(self):
        self.catalog = collections.defaultdict(list)
        self.by_arc = {}
        for arc in ARCHIVE_ORDER:
            probed = json.loads((PHASE0_REPORTS / f"{arc}.xp3.probed_entries.json").read_text("utf-8-sig"))
            self.by_arc[arc] = probed
            for e in probed:
                fh = e.get("fileHash")
                if fh:
                    self.catalog[fh].append({"archive": arc, **e})

    def find(self, name: str, exts=None, required=True):
        candidates = [name] if ("." in Path(name).name or not exts) else [name + ext for ext in exts]
        for cand in candidates:
            hits = self.catalog.get(file_hash(cand), [])
            if hits:
                # Prefer non-bgimage2 if exact name exists in multiple
                for arc in ARCHIVE_ORDER:
                    for h in hits:
                        if h["archive"] == arc:
                            return h
                return hits[0]
        if required:
            raise FileNotFoundError(f"Unresolved archive entry: {name} (tried {candidates})")
        return None

    def read_text(self, name: str) -> str:
        e = self.find(name)
        rel = Path(e["extractedFile"]).name
        p = PROBE / "decoded" / "text" / e["archive"] / rel
        return p.read_text("utf-8")

    def read_s0(self, name: str):
        e = self.find(name)
        rel = Path(e["extractedFile"]).with_suffix(".pbd.json").name
        p = PROBE / "decoded" / "s0" / e["archive"] / rel
        return json.loads(p.read_text("utf-8")), e

    def extract_item(self, e: dict, ext_override=None):
        ext = ext_override or Path(e.get("resolvedName") or "").suffix.lower() or e.get("extGuess") or ".bin"
        out = ROOT / "probe" / "raw" / e["archive"] / f"{e['index']:05d}{ext}"
        return {
            "archive": e["archive"] + ".xp3",
            "index": e["index"],
            "name": e.get("resolvedName") or f"{e['archive']}_{e['index']}",
            "kind": e.get("kind"),
            "original": e.get("original", 0),
            "width": e.get("width"),
            "height": e.get("height"),
            "hasAlpha": e.get("hasAlpha"),
            "output": str(out),
        }


def main():
    cat = ArchiveCatalog()
    requests = json.loads((CONV / "image-requests.json").read_text("utf-8"))

    def ensure_request(file_name, options=None, composite=None):
        data = {"file": file_name, "options": options or {}}
        if composite:
            data["composite"] = composite
        aid = hashlib.sha256(compact(data).encode("utf-8")).hexdigest()[:16]
        if aid in requests:
            assert requests[aid] == data
        else:
            requests[aid] = data
        return aid

    # 1. Parse CG gallery (patch_cr_data cglist_1.csv -> 32 groups, 134 variants)
    cg_groups = []
    for row in csv.reader(cat.read_text("cglist_1.csv").splitlines()):
        if not row or not row[0].startswith(("thum_ev", "thum_sdcom")):
            continue
        group = {"id": row[0][5:], "variants": []}
        for cell in row[2:]:
            cell = cell.strip()
            if not cell:
                continue
            parts = cell.split("|")
            fg = parts[0].split("?", 1)[0]
            flag = parts[0].split("?", 1)[1] if "?" in parts[0] else fg
            if len(parts) > 1:
                bg = parts[1]
                aid = ensure_request(fg, composite=[bg, fg])
                if len(parts) > 2 and parts[2].startswith("*"):
                    flag = parts[2][1:]
            else:
                aid = ensure_request(fg)
            group["variants"].append({"asset": aid, "flag": flag, "label": fg})
        cg_groups.append(group)
    assert len(cg_groups) == 32, f"Expected 32 CG groups, got {len(cg_groups)}"
    assert sum(len(g["variants"]) for g in cg_groups) == 134, "Expected 134 CG variants"

    # 2. Load CN localized image renames (imagenamemap.txt)
    cn_renames = {}
    for line in cat.read_text("imagenamemap.txt").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cols = re.split(r"\t+", line)
        if len(cols) >= 3 and cols[2] in ('CurrentLanguageTag=="cn"', 'CurrentLanguageUITag=="cn"'):
            cn_renames[cols[0].lower()] = cols[1]

    selected_extracts = {}

    def record_extract(e, ext_override=None):
        key = f"{e['archive']}:{e['index']}"
        if key not in selected_extracts:
            selected_extracts[key] = cat.extract_item(e, ext_override=ext_override)
        return selected_extracts[key]

    def resolve_static_entry(raw_name: str):
        name = cn_renames.get(raw_name.lower(), raw_name)
        if name.lower() in STATIC_FALLBACKS:
            name = STATIC_FALLBACKS[name.lower()]
        e = cat.find(name, exts=(".png", ".tlg", ".jpg", ".jpeg"), required=False)
        # Prefer 1280x720 non-'l' base when exact hit is a 2560x1440 bgimage2 duplicate and non-'l' base exists in bgimage/cr_event/patch
        if e is not None and e["archive"] == "bgimage2" and name.lower().endswith("l"):
            base_name = name[:-1]
            base_hit = cat.find(base_name, exts=(".png", ".tlg", ".jpg", ".jpeg"), required=False)
            if base_hit and base_hit["archive"] in ("bgimage", "cr_event", "patch", "patch_cr_data", "data"):
                e = base_hit
        if e is None and name.lower().endswith("l"):
            e = cat.find(name[:-1], exts=(".png", ".tlg", ".jpg", ".jpeg"), required=False)
        if e is None:
            raise FileNotFoundError(f"Missing static image {raw_name!r} (mapped {name!r})")
        rec = record_extract(e)
        return {
            "archive": e["archive"],
            "entry": e["index"],
            "name": e.get("resolvedName") or name,
            "kind": e["kind"],
            "width": e.get("width"),
            "height": e.get("height"),
            "hasAlpha": e.get("hasAlpha"),
            "raw": rec["output"],
        }

    # 3. Portrait table cache (_s scale)
    sinfo_cache = {}
    stand_cache = {}

    def load_model_table(base: str):
        if base in sinfo_cache:
            return sinfo_cache[base]
        sinfo_txt = cat.read_text(base + ".sinfo")
        base_layers = collections.defaultdict(list)
        pose_layers = collections.defaultdict(list)
        faces = collections.defaultdict(list)
        aliases = {}
        for row in csv.reader(sinfo_txt.splitlines(), delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            if row[0] == "dress" and len(row) >= 4:
                if row[2] == "base":
                    base_layers[row[1]].append(row[3])
                elif row[2] == "diff":
                    pose_layers[(row[1], row[3])].append(row[4])
            elif row[0] == "fgname":
                if row[2] not in faces[row[1]]:
                    faces[row[1]].append(row[2])
            elif row[0] == "fgalias":
                aliases[row[1]] = row[2:]
        pbd, pbd_entry = cat.read_s0(base + "_s.pbd")
        byid = {l["layer_id"]: l for l in pbd[1:] if "layer_id" in l}
        bypath = {}

        def layer_path(l):
            par = l.get("group_layer_id")
            return (layer_path(byid[par]) + "/" if par in byid else "") + l["name"].replace("/", "_")

        for order, l in enumerate(pbd[1:]):
            if "layer_id" in l:
                bypath[layer_path(l)] = {**l, "order": order}
        val = {
            "base": base_layers,
            "pose": pose_layers,
            "faces": faces,
            "aliases": aliases,
            "bypath": bypath,
            "canvas": pbd[0],
            "pbd": f"{pbd_entry['archive']}:{pbd_entry['index']}",
        }
        sinfo_cache[base] = val
        return val

    # 4. Resolve every request
    statics = {}
    portraits = {}
    failures = []
    unique_bodies = set()

    for aid, req in requests.items():
        try:
            f = req["file"]
            low = f.lower()
            if low in SOLID_MAP:
                statics[aid] = {"type": "solid", **SOLID_MAP[low]}
                continue
            if low.startswith("color,"):
                # parse color,0xAARRGGBB,width,W,height,H
                parts = f.split(",")
                kv = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)} if len(parts) >= 6 else {}
                w = int(kv.get("width", 1280))
                h = int(kv.get("height", 720))
                col = int(parts[1], 16)
                statics[aid] = {"type": "solid", "color": [(col >> 16) & 255, (col >> 8) & 255, col & 255], "size": [w, h]}
                continue
            if "composite" in req:
                layers = []
                for lf in req["composite"]:
                    if lf.lower() in SOLID_MAP:
                        layers.append({"type": "solid", **SOLID_MAP[lf.lower()]})
                    else:
                        layers.append({"type": "image", **resolve_static_entry(lf)})
                statics[aid] = {"type": "composite", "layers": layers}
                continue
            if not f.endswith(".stand"):
                statics[aid] = {"type": "static", "image": resolve_static_entry(f)}
                continue

            if f not in stand_cache:
                stand_cache[f] = loads(cat.read_text(f))
            op = req["options"] or {}
            if not op and f in ("呪いＡ.stand", "呪いＢ.stand", "呪いＣ.stand", "呪いＤ.stand"):
                op = GHOST_DEFAULT_OPTIONS
            dress = str(op.get("dress", ""))
            pose = str(op.get("pose", ""))
            face = str(op.get("face", ""))
            assert dress and pose, (f, op)
            found = None
            for definition in stand_cache[f]:
                base = definition["filename"]
                tbl = load_model_table(base)
                if (dress, pose) in tbl["pose"]:
                    found = (definition, base, tbl)
                    break
            if found is None:
                raise ValueError(f"No dress/pose rule for {(f, op)}")
            definition, base, tbl = found
            bodypaths = tbl["base"].get(dress, []) + tbl["pose"][(dress, pose)]
            tokens = face.split(":") if ":" in face else tbl["aliases"].get(face, [face])
            facepaths = []
            for tok in tokens:
                if not tok:
                    continue
                if tok not in tbl["faces"]:
                    raise ValueError(f"Unknown face token {(base, tok)}")
                facepaths.extend(tbl["faces"][tok])
            layers = []
            for lp in dict.fromkeys(bodypaths + facepaths):
                if lp == "dummy":
                    continue
                l = tbl["bypath"].get(lp)
                if l is None or l.get("layer_type") != 0:
                    raise ValueError(f"Unusable PBD layer {(base, lp)}")
                layer_name = f"{base}_s_{l['layer_id']}"
                e = cat.find(layer_name, exts=(".tlg", ".png"))
                rec = record_extract(e)
                is_face = (lp in facepaths) and (lp not in bodypaths)
                layers.append(
                    {
                        "path": lp,
                        "face": is_face,
                        "raw": rec["output"],
                        "kind": e["kind"],
                        "left": l["left"],
                        "top": l["top"],
                        "width": l["width"],
                        "height": l["height"],
                        "type": l["type"],
                        "opacity": l["opacity"],
                        "order": l["order"],
                    }
                )
            unique_bodies.add((base, dress, pose, tuple(bodypaths)))
            portraits[aid] = {
                "base": base,
                "canvas": tbl["canvas"],
                "dress": dress,
                "pose": pose,
                "face": face,
                "layers": sorted(layers, key=lambda item: -item["order"]),
            }
        except Exception as err:
            failures.append({"asset": aid, "request": req, "error": str(err)})

    # 5. Also add UI & Font extractions (SourceHanSansSC-Regular.otf, title_base.png, logo.png, title__pack.tlg)
    extra_ui = {}
    for ui_key, ui_name in [
        ("font", "sourcehansanssc-regular.otf"),
        ("title_bg", "title_base.png"),
        ("title_logo", "eyecatch/logo.png"),
        ("title_pack", "title__pack.tlg"),
    ]:
        hit = cat.find(ui_name, required=False)
        if hit:
            ext = Path(ui_name).suffix.lower()
            extra_ui[ui_key] = record_extract(hit, ext_override=ext)

    (CONV / "image-requests.json").write_text(compact(requests), "utf-8")
    (CONV / "gallery.json").write_text(compact(cg_groups), "utf-8")
    (REPORTS / "portrait-plan.json").write_text(json.dumps(portraits, ensure_ascii=False, indent=2), "utf-8")
    (REPORTS / "static-image-plan.json").write_text(json.dumps(statics, ensure_ascii=False, indent=2), "utf-8")
    (REPORTS / "ui-font-extracts.json").write_text(json.dumps(extra_ui, ensure_ascii=False, indent=2), "utf-8")
    (REPORTS / "image-plan-failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), "utf-8")
    (REPORTS / "extraction-plan.json").write_text(json.dumps(list(selected_extracts.values()), ensure_ascii=False, indent=2), "utf-8")

    est_entries = 15 + 106 + len(statics) + len(unique_bodies) + (len(portraits) + 3) // 4
    summary = {
        "requests": len(requests),
        "portraits": len(portraits),
        "uniquePortraitBodies": len(unique_bodies),
        "statics": len(statics),
        "cgGroups": len(cg_groups),
        "cgVariants": sum(len(g["variants"]) for g in cg_groups),
        "uniqueRawExtracts": len(selected_extracts),
        "rawExtractBytes": sum(x["original"] for x in selected_extracts.values()),
        "failures": len(failures),
        "estimatedRpkEntries": est_entries,
        "extraUiKeys": list(extra_ui.keys()),
    }
    (REPORTS / "image-plan-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    print(compact(summary))
    if failures:
        print("FAILURES:", compact(failures[:10]))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
