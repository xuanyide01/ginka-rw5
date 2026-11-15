"""Prepare all GINKA Watch 5 images: 432x243 BGs/CGs (JPEG), deduplicated portrait bodies + quantized expression atlases (PNG), gallery.txt, and UI icons."""
from pathlib import Path
import hashlib
import io
import json
import math
import os
import shutil

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(r"E:\Antigravity\ginka-rw5")
RAW_ROOT = ROOT / "probe" / "raw"
TLG_PNG_ROOT = ROOT / "probe" / "decoded_tlg"
CONV = ROOT / "converted"
REPORTS = ROOT / "reports"
IMG_DEST = ROOT / "src" / "common" / "images"
FACE_DEST = ROOT / "src" / "common" / "faces"
COMMON = ROOT / "src" / "common"

JPEG_QUALITY = int(os.environ.get("GINKA_JPEG_QUALITY", "54"))
JPEG_SUBSAMPLING = int(os.environ.get("GINKA_JPEG_SUBSAMPLING", "2"))
CG_QUALITY = int(os.environ.get("GINKA_CG_QUALITY", "70"))
CG_SUBSAMPLING = int(os.environ.get("GINKA_CG_SUBSAMPLING", "0"))
BODY_COLORS = int(os.environ.get("GINKA_BODY_COLORS", "256"))
ATLAS_COLORS = int(os.environ.get("GINKA_ATLAS_COLORS", "256"))
ATLAS_BATCH = int(os.environ.get("GINKA_ATLAS_BATCH", "2"))


def compact(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def raw_to_image_path(raw_str: str) -> Path:
    p = Path(raw_str)
    if p.suffix.lower() == ".tlg":
        rel = p.relative_to(RAW_ROOT).with_suffix(".png")
        return TLG_PNG_ROOT / rel
    return p


class ImageStore:
    def __init__(self):
        for d in (IMG_DEST, FACE_DEST):
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
        self.serial = 0
        self.by_hash = {}
        self.by_rgb_digest = {}
        self.bytes_total = 0

    def save_bytes(self, raw_bytes: bytes, ext: str) -> str:
        h = hashlib.sha256(raw_bytes).hexdigest()
        if h not in self.by_hash:
            n = self.serial
            self.serial += 1
            rel = f"{n // 48:02d}/{n % 48:02d}.{ext}"
            out = IMG_DEST / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(raw_bytes)
            self.by_hash[h] = "/common/images/" + rel
            self.bytes_total += len(raw_bytes)
        return self.by_hash[h]

    def store_jpeg(self, im: Image.Image, quality: int = JPEG_QUALITY, subsampling: int = JPEG_SUBSAMPLING) -> str:
        if im.mode != "RGB":
            if im.mode == "RGBA":
                back = Image.new("RGB", im.size, (0, 0, 0))
                back.paste(im, mask=im.getchannel("A"))
                im = back
            else:
                im = im.convert("RGB")
        # Deduplicate pixel-identical 432x243 frames so composites matching gallery CGs share the higher-quality file
        rgb_digest = hashlib.sha256(im.tobytes()).hexdigest()
        if rgb_digest in self.by_rgb_digest:
            return self.by_rgb_digest[rgb_digest]
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True, subsampling=subsampling)
        uri = self.save_bytes(buf.getvalue(), "jpg")
        self.by_rgb_digest[rgb_digest] = uri
        return uri

    def store_png(self, im: Image.Image, colors=BODY_COLORS) -> str:
        q = im.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        buf = io.BytesIO()
        q.save(buf, format="PNG", optimize=True)
        return self.save_bytes(buf.getvalue(), "png")


def main():
    statics_plan = json.loads((REPORTS / "static-image-plan.json").read_text("utf-8"))
    portraits_plan = json.loads((REPORTS / "portrait-plan.json").read_text("utf-8"))
    gallery_plan = json.loads((CONV / "gallery.json").read_text("utf-8"))
    ui_extracts = json.loads((REPORTS / "ui-font-extracts.json").read_text("utf-8"))

    store = ImageStore()
    layer_cache = {}

    def open_rgba(path: Path) -> Image.Image:
        key = str(path)
        if key not in layer_cache:
            if len(layer_cache) > 180:
                layer_cache.clear()
            layer_cache[key] = Image.open(path).convert("RGBA")
        return layer_cache[key]

    def load_static_layer(spec: dict, base_size=(1280, 720)) -> Image.Image:
        if spec.get("type") == "solid":
            w, h = spec.get("size", list(base_size))
            return Image.new("RGBA", (w, h), tuple(spec["color"]) + (255,))
        im = open_rgba(raw_to_image_path(spec["raw"])).copy()
        return im

    def normalize_backdrop(im: Image.Image, name: str = "") -> Image.Image:
        # 2x HD zoom assets (*l) are double resolution; normalize to 1x coordinates first
        if im.width >= 2400:
            im = im.resize((im.width // 2, max(1, round(im.height * 0.5))), Image.Resampling.LANCZOS)
        w, h = im.size
        if (w, h) == (1280, 720):
            return im
        if w == 1280 and h == 721:
            return im.crop((0, 0, 1280, 720))
        if w > 1280 and h == 720:
            # Wide panoramic background -> centered 1280x720 desktop viewport
            ox = (w - 1280) // 2
            return im.crop((ox, 0, ox + 1280, 720))
        if w == 1280 and h > 720:
            # Stacked twin sunburst (bgi_appare) has horizontal seam at y=720; take top intact frame
            if name == "bgi_appare":
                return im.crop((0, 0, 1280, 720))
            oy = (h - 720) // 2
            return im.crop((0, oy, 1280, oy + 720))
        if w < 1280 or h < 720:
            # Smaller cut-in overlay (e.g. gin_katana 1087x615): center onto transparent 1280x720 canvas
            canvas = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
            ox = (1280 - w) // 2
            oy = (720 - h) // 2
            canvas.paste(im.crop((max(0, -ox), max(0, -oy), min(w, 1280 - ox), min(h, 720 - oy))), (max(0, ox), max(0, oy)))
            return canvas
        # Fallback center crop after aspect-preserving scale
        scale = max(1280.0 / w, 720.0 / h)
        scaled = im.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
        ox = (scaled.width - 1280) // 2
        oy = (scaled.height - 720) // 2
        return scaled.crop((ox, oy, ox + 1280, oy + 720))

    def is_opaque_full_layer(im: Image.Image) -> bool:
        hist = im.getchannel("A").histogram()
        opaque = sum(hist[240:])
        return (opaque / (im.width * im.height)) >= 0.98

    gallery_aids = {v["asset"] for g in gallery_plan for v in g["variants"]}
    def is_cg_plan(aid: str, plan: dict) -> bool:
        if aid in gallery_aids:
            return True
        if plan["type"] == "static":
            return str(plan["image"].get("name", "")).lower().startswith("ev")
        if plan["type"] == "composite":
            return any(str(lf.get("name", "")).lower().startswith("ev") for lf in plan.get("layers", []))
        return False

    # Deduplicate identical static plans first, prioritizing highest quality if shared with gallery/event CGs
    static_raw_cache = {}
    mapping = {}

    # 1. Process static & composite images -> exact 432x243 (16:9) JPEG (CGs use higher quality + 4:4:4 chroma)
    ordered_statics = sorted(statics_plan.items(), key=lambda kv: (0 if is_cg_plan(kv[0], kv[1]) else 1, kv[0]))
    for aid, plan in ordered_statics:
        plan_key = json.dumps(plan, sort_keys=True, ensure_ascii=False)
        if plan_key in static_raw_cache:
            mapping[aid] = dict(static_raw_cache[plan_key])
            continue
        is_cg = is_cg_plan(aid, plan)
        q = CG_QUALITY if is_cg else JPEG_QUALITY
        sub = CG_SUBSAMPLING if is_cg else JPEG_SUBSAMPLING
        kind = plan["type"]
        if kind == "solid":
            rgb = Image.new("RGB", (432, 243), tuple(plan["color"]))
            src = store.store_jpeg(rgb, quality=q, subsampling=sub)
            meta = {"src": src, "width": 432, "height": 243, "portrait": False}
        elif kind == "static":
            im = normalize_backdrop(load_static_layer(plan["image"]), plan["image"].get("name", ""))
            im = im.resize((432, 243), Image.Resampling.LANCZOS)
            src = store.store_jpeg(im, quality=q, subsampling=sub)
            meta = {"src": src, "width": 432, "height": 243, "portrait": False}
        elif kind == "composite":
            # Deduplicate identical consecutive layers before normalizing to 1280x720
            dedup_specs = []
            for lf in plan["layers"]:
                key = (lf.get("type"), lf.get("name"), tuple(lf.get("color", ())))
                if not dedup_specs or dedup_specs[-1][0] != key:
                    dedup_specs.append((key, lf))
            base = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
            for _, lf in dedup_specs:
                ov = normalize_backdrop(load_static_layer(lf), lf.get("name", ""))
                if is_opaque_full_layer(ov):
                    # Opaque full-screen CGI/BG completely replaces all underlayers with clean black matte on 1px AA rim
                    fresh = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
                    fresh.alpha_composite(ov)
                    base = fresh
                else:
                    base.alpha_composite(ov)
            out = base.resize((432, 243), Image.Resampling.LANCZOS)
            src = store.store_jpeg(out, quality=q, subsampling=sub)
            meta = {"src": src, "width": 432, "height": 243, "portrait": False}
        static_raw_cache[plan_key] = meta
        mapping[aid] = dict(meta)

    # 2. Process portraits -> body PNG + deduplicated raw patches (packed into 2x2 atlases)
    patch_by_hash = {}
    unique_patches = []  # list of (hash, Image)
    portrait_pending = {}

    for aid, plan in portraits_plan.items():
        selected = []
        for l in plan["layers"]:
            im = open_rgba(raw_to_image_path(l["raw"]))
            if l["opacity"] != 255:
                im = im.copy()
                im.putalpha(im.getchannel("A").point(lambda n, op=l["opacity"]: n * op // 255))
            selected.append((l, im))

        x0 = min(l["left"] for l, _ in selected)
        y0 = min(l["top"] for l, _ in selected)
        x1 = max(l["left"] + im.width for l, im in selected)
        y1 = max(l["top"] + im.height for l, im in selected)

        face_layers = [(l, im) for l, im in selected if l["face"]]
        face_bottom = max((l["top"] + im.height for l, im in face_layers), default=y0 + 200)
        canvas_w = plan["canvas"]["width"]
        crop_h = min(y1 - y0, max(face_bottom - y0 + 80, round(canvas_w * 0.68)))

        full_im = Image.new("RGBA", (x1 - x0, crop_h))
        body_im = Image.new("RGBA", (x1 - x0, crop_h))
        for l, im in selected:
            pos = (l["left"] - x0, l["top"] - y0)
            # All GINKA PBD layers use type 13 (alpha normal); crop naturally clips bottom overflow
            full_im.alpha_composite(im, pos)
            if not l["face"]:
                body_im.alpha_composite(im, pos)

        # Preserve relative scale between small creatures and full-height characters within 243px CG stage
        scale = min(236.0 / crop_h, 0.49) if crop_h < 400 else 236.0 / crop_h
        out_w = max(1, round(full_im.width * scale))
        out_h = max(1, round(full_im.height * scale))
        full_scaled = full_im.resize((out_w, out_h), Image.Resampling.LANCZOS)
        body_scaled = body_im.resize((out_w, out_h), Image.Resampling.LANCZOS)

        diff = ImageChops.difference(full_scaled, body_scaled)
        bands = diff.split()
        mask = ImageChops.lighter(ImageChops.lighter(bands[0], bands[1]), ImageChops.lighter(bands[2], bands[3]))
        pbox = mask.getbbox()

        body_src = store.store_png(body_scaled, colors=BODY_COLORS)
        entry = {
            "src": body_src,
            "width": out_w,
            "height": out_h,
            "portrait": True,
        }
        if pbox:
            patch_im = full_scaled.crop(pbox)
            buf = io.BytesIO()
            patch_im.save(buf, format="PNG")
            ph = hashlib.sha256(buf.getvalue()).hexdigest()
            if ph not in patch_by_hash:
                patch_by_hash[ph] = len(unique_patches)
                unique_patches.append((ph, patch_im))
            portrait_pending[aid] = (entry, ph, pbox, patch_im.size)
        else:
            mapping[aid] = entry

    # Pack adjacent unique patches in compact horizontal pairs (1x2, or 1x1 when ATLAS_BATCH=1)
    # so each expression keeps high 256-color fidelity with low decode RAM and compact PNG overhead.
    patch_file_loc = {}
    atlas_count = 0
    face_bytes = 0
    batch_n = max(1, ATLAS_BATCH)
    for start in range(0, len(unique_patches), batch_n):
        batch = unique_patches[start : start + batch_n]
        aw = sum(pim.width for _, pim in batch)
        ah = max(pim.height for _, pim in batch)
        atlas = Image.new("RGBA", (aw, ah))
        rel = f"/common/faces/{atlas_count // 48:02d}/{atlas_count % 48:02d}.png"
        ax = 0
        for ph, pim in batch:
            atlas.paste(pim, (ax, 0))
            patch_file_loc[ph] = (rel, aw, ah, ax, 0)
            ax += pim.width
        out_p = FACE_DEST / f"{atlas_count // 48:02d}/{atlas_count % 48:02d}.png"
        out_p.parent.mkdir(parents=True, exist_ok=True)
        q = atlas.quantize(colors=ATLAS_COLORS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        q.save(out_p, format="PNG", optimize=True)
        face_bytes += out_p.stat().st_size
        atlas_count += 1

    for aid, (entry, ph, pbox, (pw, ph_px)) in portrait_pending.items():
        rel, fw, fh, ax, ay = patch_file_loc[ph]
        entry["patch"] = rel
        entry["patchRect"] = [pbox[0], pbox[1], pw, ph_px]
        entry["patchAtlas"] = [fw, fh, ax, ay]
        mapping[aid] = entry

    # 3. Generate gallery.txt
    gallery_out = [
        {"label": g["id"].upper(), "variants": [mapping[v["asset"]]["src"] for v in g["variants"]]}
        for g in gallery_plan
    ]
    gallery_path = COMMON / "gallery.txt"
    gallery_path.write_text(compact(gallery_out), "utf-8")

    # 4. Refresh title_logo.png (title backgrounds and circular face-cropped logo.png are built by build_ui_assets.py)
    logo_raw = open_rgba(raw_to_image_path(ui_extracts["title_logo"]["output"]))
    bbox = logo_raw.getbbox()
    logo_trim = logo_raw.crop(bbox) if bbox else logo_raw
    logo_trim.thumbnail((300, 90), Image.Resampling.LANCZOS)
    tlogo_path = COMMON / "title_logo.png"
    logo_trim.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(tlogo_path, optimize=True)

    icon_path = COMMON / "logo.png"
    old_tbg = COMMON / "title_bg.jpg"
    if old_tbg.exists():
        old_tbg.unlink()

    (CONV / "image-map.json").write_text(compact(mapping), "utf-8")

    # 5. Compute full asset & entry budget
    story_files = list((COMMON / "story").rglob("*.txt"))
    img_files = list(IMG_DEST.rglob("*"))
    img_files = [p for p in img_files if p.is_file()]
    face_files = [p for p in FACE_DEST.rglob("*.png") if p.is_file()]
    story_bytes = sum(p.stat().st_size for p in story_files)
    img_bytes = sum(p.stat().st_size for p in img_files)
    ui_bytes = tlogo_path.stat().st_size + (icon_path.stat().st_size if icon_path.exists() else 0) + gallery_path.stat().st_size

    budget = {
        "jpegQuality": JPEG_QUALITY,
        "cgQuality": CG_QUALITY,
        "requestsMapped": len(mapping),
        "staticFiles": len([p for p in img_files if p.suffix == ".jpg"]),
        "bodyFiles": len([p for p in img_files if p.suffix == ".png"]),
        "uniqueExpressionPatches": len(unique_patches),
        "expressionAtlasSlotSize": "1x1",
        "expressionAtlasSize": "per-patch",
        "expressionAtlasFiles": len(face_files),
        "storyChunkFiles": len(story_files),
        "bytes": {
            "storyJsonUncompressed": story_bytes,
            "images": img_bytes,
            "faces": face_bytes,
            "uiAndGallery": ui_bytes,
        },
        "totalEntriesBeforeFontAndApp": len(story_files) + len(img_files) + len(face_files) + 3,
    }
    (REPORTS / "budget.json").write_text(json.dumps(budget, ensure_ascii=False, indent=2), "utf-8")
    print(compact(budget))


if __name__ == "__main__":
    main()
