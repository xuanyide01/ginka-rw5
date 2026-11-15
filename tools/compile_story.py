"""Compile all 38 official GINKA .ks.scn scripts (CN slot) for REDMI Watch 5."""
from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT = Path(r"E:\Antigravity\ginka-rw5")
PHASE0_PSB = Path(r"E:\Antigravity\probe\decoded\psb\patch_cr_data")
CONV = ROOT / "converted"
STORY_DIR = ROOT / "src" / "common" / "story"
REPORTS = ROOT / "reports"

CONV.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)
if STORY_DIR.exists():
    shutil.rmtree(STORY_DIR)
STORY_DIR.mkdir(parents=True, exist_ok=True)

POS_X = {
    "cx_c": 0,
    "cx2_l": -240,
    "cx2_r": 240,
    "cx3_l": -426,
    "cx3_r": 426,
}

# Overlay / transition helpers that are translucent masks/wipes/transparent rects rather than solid backdrops
SKIP_OVERLAY_PREFIXES = ("mask_", "wipe", "clip_", "parts_")


def compact(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def normalize_text(text):
    return (
        (text or "")
        .replace("\\n", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
        .replace("\ufffd", "…")
        .strip("\ufeff\u200b\n")
    )


def script_sort_key(name):
    if name == "after.ks":
        return (2, 0, "")
    m = re.match(r"scn(\d+)(.*)\.ks", name)
    if m:
        return (0, int(m.group(1)), m.group(2))
    return (1, 0, name)


def sid(name, label):
    return Path(name).stem + "__" + label.lstrip("*")


def main():
    scripts = []
    for p in sorted(PHASE0_PSB.glob("*.json")):
        d = json.loads(p.read_text("utf-8"))
        name = d.get("name", "")
        if "scenes" not in d or name.startswith("pro_"):
            continue
        scripts.append((p, d))
    scripts.sort(key=lambda pair: script_sort_key(pair[1]["name"]))
    assert len(scripts) == 38, f"Expected 38 official scripts, got {len(scripts)}"

    ids = {}
    for _, o in scripts:
        for sc in o["scenes"]:
            key = (o["name"].lower(), sc["label"].lower())
            assert key not in ids, f"Duplicate scene {key}"
            ids[key] = sid(o["name"], sc["label"])

    def dest(storage, target=""):
        if storage.lower() == "start.ks":
            assert target == "*gameend_title", (storage, target)
            return "@end"
        if not target:
            target = next(
                o["scenes"][0]["label"]
                for _, o in scripts
                if o["name"].lower() == storage.lower()
            )
        return ids[(storage.lower(), target.lower())]

    images = {}

    def request_asset(file, options=None, composite=None):
        data = {"file": file, "options": options or {}}
        if composite:
            data["composite"] = composite
        key = hashlib.sha256(compact(data).encode("utf-8")).hexdigest()[:16]
        if key in images:
            assert images[key] == data, (key, images[key], data)
        images[key] = data
        return key

    def is_skip_bg_layer(file_name, opacity):
        low = file_name.lower()
        if low.startswith("color,0x00"):
            return True
        if low.startswith(SKIP_OVERLAY_PREFIXES):
            return True
        if low == "bgi_moyav" and opacity < 240:
            return True
        if opacity < 180:
            return True
        return False

    def extract_art(env):
        active = []
        for slot, cls, obj in env.get("data", []) or []:
            if cls in ("bgm", "loopse", "se", "msgwin", "emotion", "bgeffect"):
                continue
            if obj.get("showmode") not in (1, 3):
                continue
            redraw = obj.get("redraw") or {}
            im = redraw.get("imageFile") or {}
            file_name = im.get("file") or ""
            if not file_name:
                continue
            ac = obj.get("action") or []
            flat = {
                a[0]: a[1]
                for a in ac
                if isinstance(a, list) and len(a) > 1 and isinstance(a[1], (int, float, str))
            }
            opacity = int(flat.get("opacity", 255))
            if opacity == 0:
                continue
            zpos = float(flat.get("zpos", 233.0 if cls == "stage" else 0.0))
            active.append(
                {
                    "slot": slot,
                    "cls": cls,
                    "file": file_name,
                    "options": im.get("options") or {},
                    "posName": redraw.get("posName"),
                    "action": flat,
                    "z": zpos,
                    "opacity": opacity,
                }
            )

        # Pick backdrop candidates from stage + non-mask opaque/semiopaque event
        bg_layers = []
        for o in active:
            if o["cls"] == "stage":
                if not is_skip_bg_layer(o["file"], o["opacity"]):
                    bg_layers.append(o)
            elif o["cls"] == "event":
                if not is_skip_bg_layer(o["file"], o["opacity"]):
                    bg_layers.append(o)

        if not bg_layers:
            bg_id = request_asset("lay_black")
            bg_z = 999.0
        else:
            # Sort back-to-front (largest zpos first)
            bg_layers.sort(key=lambda o: (-o["z"], 0 if o["cls"] == "stage" else 1))
            # If the front-most event is a full CG/cut-in (e.g. ev0*, ci*) and has a stage underneath,
            # plan_images will check if the front layer has alpha (e.g., sdcom over bg006) or is opaque.
            if len(bg_layers) == 1:
                top_bg = bg_layers[-1]
                bg_id = request_asset(top_bg["file"], top_bg["options"])
                bg_z = top_bg["z"]
            else:
                stack = [o["file"] for o in bg_layers]
                top_bg = bg_layers[-1]
                bg_id = request_asset(top_bg["file"], top_bg["options"], composite=stack)
                bg_z = top_bg["z"]

        sprites = []
        for o in sorted(active, key=lambda item: -item["z"]):
            if o["cls"] not in ("bu", "character"):
                continue
            if o["z"] > bg_z:
                continue
            ac = o["action"]
            xpos = int(round(float(ac.get("xpos", POS_X.get(o["posName"], 0)))))
            ypos = int(round(float(ac.get("ypos", 0))))
            zx = int(round(float(ac.get("zoomx", 100))))
            zy = int(round(float(ac.get("zoomy", 100))))
            sp = {"id": request_asset(o["file"], o["options"])}
            if xpos:
                sp["x"] = xpos
            if ypos:
                sp["y"] = ypos
            if zx != 100:
                sp["zx"] = zx
            if zy != 100:
                sp["zy"] = zy
            if o["opacity"] != 255:
                sp["op"] = o["opacity"]
            sprites.append(sp)

        return {"bg": bg_id, "sp": sprites}

    def cond_expr(exp):
        s = (exp or "").strip()
        if not s:
            return None
        m = re.fullmatch(r"f\.flag\s*(==|>=|<)\s*(\d+)", s)
        assert m, f"Unexpected next eval: {exp!r}"
        return ["flag", m[1], int(m[2])]

    def eff_expr(exp):
        s = (exp or "").strip()
        if not s:
            return []
        m = re.fullmatch(r"f\.flag\s*=\s*(\d+)", s)
        if m:
            return [["set", "flag", int(m[1])]]
        m = re.fullmatch(r"f\.flag\s*=\s*f\.flag\s*\+\s*(\d+)", s)
        assert m, f"Unexpected select exp: {exp!r}"
        return [["add", "flag", int(m[1])]]

    nodes = {}
    source_map = []
    per_script = []
    movie_events = []
    chunk_serial = 0
    total_texts = 0
    max_chunk_bytes = 0
    max_sprites = 0

    for src_path, o in scripts:
        script_name = o["name"]
        subtotal = 0
        digest = hashlib.sha256()
        for sc in o["scenes"]:
            node_id = ids[(script_name.lower(), sc["label"].lower())]
            title = sc.get("title") or ["", "", "", ""]
            chapter = (title[2] if isinstance(title, list) else title) or ""
            frames = []
            for idx, t in enumerate(sc.get("texts", [])):
                cn = t[1][2]
                assert cn is not None and len(cn) >= 2, (script_name, sc["label"], idx)
                speaker = (cn[0] or "").strip()
                text = normalize_text(cn[1] or "")
                art = extract_art(t[4])
                max_sprites = max(max_sprites, len(art["sp"]))
                frame = {"s": speaker, "t": text, "bg": art["bg"], "sp": art["sp"]}
                frames.append(frame)
                source_map.append([node_id, idx, script_name, sc["label"], idx])
                digest.update(compact([cn[0] or "", cn[1] or ""]).encode("utf-8"))
                subtotal += 1
                total_texts += 1

            choices = []
            for opt in sc.get("selects", []) or []:
                assert not opt.get("eval"), opt
                cn_opt = opt["language"][2]
                assert cn_opt and cn_opt.get("text") is not None, opt
                choices.append(
                    {
                        "text": normalize_text(cn_opt["text"]),
                        "to": dest(opt["storage"], opt.get("target", "")),
                        "effects": eff_expr(opt.get("exp", "")),
                    }
                )

            nexts = [
                {"to": dest(n["storage"], n.get("target", "")), "when": cond_expr(n.get("eval", ""))}
                for n in sc.get("nexts", []) or []
            ]

            complete = []
            if any(n["to"] == "@end" for n in nexts):
                complete = [{"scn015.ks": "start", "scn114.ks": "next", "after.ks": "after"}.get(script_name, Path(script_name).stem)]

            # Split frames into <= 30,720 byte chunks stored in sharded subdirs
            chunks = []
            pending = []
            cur_bytes = 2

            def flush():
                nonlocal chunk_serial, max_chunk_bytes, pending, cur_bytes
                if not pending:
                    return
                rel = f"{chunk_serial // 48:02d}/{chunk_serial % 48:02d}.txt"
                out_file = STORY_DIR / rel
                out_file.parent.mkdir(parents=True, exist_ok=True)
                raw = compact(pending).encode("utf-8")
                assert len(raw) <= 30720, (node_id, len(raw))
                out_file.write_bytes(raw)
                max_chunk_bytes = max(max_chunk_bytes, len(raw))
                chunks.append({"file": rel, "count": len(pending), "bytes": len(raw)})
                chunk_serial += 1
                pending = []
                cur_bytes = 2

            for fr in frames:
                sz = len(compact(fr).encode("utf-8")) + (1 if pending else 0)
                if pending and cur_bytes + sz > 30720:
                    flush()
                    sz = len(compact(fr).encode("utf-8"))
                assert sz + 2 <= 30720, (node_id, sz)
                pending.append(fr)
                cur_bytes += sz
            flush()

            route = (
                "after"
                if script_name == "after.ks"
                else "next"
                if script_name.startswith("scn1")
                else "bad"
                if script_name.startswith("scn9")
                else "start"
            )
            nodes[node_id] = {
                "title": chapter,
                "route": route,
                "count": len(frames),
                "chunks": chunks,
                "choices": choices,
                "next": nexts,
                "complete": complete,
                "source": [script_name, sc["label"]],
            }
            for line in sc.get("lines", []) or []:
                if isinstance(line, list) and line and line[0] == "sysmovie":
                    movie_events.append({"script": script_name, "scene": sc["label"], "command": line[0]})

        per_script.append(
            {
                "script": script_name,
                "scenes": len(o["scenes"]),
                "texts": subtotal,
                "orderedTextDigest": digest.hexdigest(),
                "sourceJson": str(src_path),
            }
        )

    nodes["@end"] = {
        "terminal": True,
        "title": "返回标题",
        "route": "system",
        "count": 0,
        "chunks": [],
        "choices": [],
        "next": [],
        "complete": [],
    }
    for nid, n in nodes.items():
        for link in n["next"] + n["choices"]:
            assert link["to"] in nodes, (nid, link)

    chapters = [
        {
            "node": ids[(o["name"].lower(), o["scenes"][0]["label"].lower())],
            "title": (o["scenes"][0].get("title") or ["", "", "", ""])[2],
            "route": nodes[ids[(o["name"].lower(), o["scenes"][0]["label"].lower())]]["route"],
            "script": o["name"],
        }
        for _, o in scripts
    ]

    graph = {
        "format": 1,
        "package": "com.antigravity.ginka.rw5",
        "initial": ids[("scn000.ks", "*start")],
        "entries": {
            "start": ids[("scn000.ks", "*start")],
            "next": ids[("scn101.ks", "*start")],
            "after": ids[("after.ks", "*start")],
        },
        "initialFlags": {"flag": 0},
        "unlock": {"next": ["start"], "after": ["next"]},
        "nodes": nodes,
        "chapters": chapters,
        "audio": False,
        "video": False,
    }

    assert total_texts == 14998, f"Expected 14998 texts, got {total_texts}"
    (CONV / "graph.json").write_text(compact(graph), "utf-8")
    (CONV / "image-requests.json").write_text(compact(images), "utf-8")
    (CONV / "source-map.json").write_text(compact(source_map), "utf-8")

    summary = {
        "status": "compiled",
        "scripts": len(scripts),
        "sceneNodes": len(nodes) - 1,
        "terminalNodes": 1,
        "texts": total_texts,
        "choiceNodes": sum(bool(n["choices"]) for n in nodes.values()),
        "choiceOptions": sum(len(n["choices"]) for n in nodes.values()),
        "chunks": chunk_serial,
        "storyBytes": sum(p.stat().st_size for p in STORY_DIR.rglob("*.txt")),
        "largestChunkBytes": max_chunk_bytes,
        "imageRequests": len(images),
        "portraits": sum(v["file"].endswith(".stand") for v in images.values()),
        "maxVisibleSprites": max_sprites,
        "omittedMovieCommands": movie_events,
        "audioOrMovieOutputFiles": 0,
        "perScript": per_script,
    }
    (REPORTS / "story-compilation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    print(compact({k: v for k, v in summary.items() if k not in ("perScript", "omittedMovieCommands")}))


if __name__ == "__main__":
    main()
