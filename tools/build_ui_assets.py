"""Build lightweight Watch-5 UI textures adapted directly from original GINKA assets."""
from pathlib import Path
import io
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(r"E:\Antigravity\ginka-rw5")
REF_DATA = ROOT / "probe" / "ui_ref_png" / "data"
REF_PATCH = ROOT / "probe" / "ui_ref_png" / "patch"
RAW_DATA = ROOT / "probe" / "raw" / "data"
TITLE_NS0 = Path(r"E:\Antigravity\probe\decoded\s0\patch\00129__94d4a97c61498621__7af5ccd2611c1726.ns0.json")
UI_OUT = ROOT / "src" / "common" / "ui"


def save_quantized_png(im: Image.Image, out_path: Path, colors: int = 96):
    """Quantize RGBA image compactly while keeping smooth alpha edges."""
    q = im.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    buf = io.BytesIO()
    q.save(buf, format="PNG", optimize=True)
    out_path.write_bytes(buf.getvalue())


def build_panel_backdrop():
    """Adapt data_1989 polygonal ocean-crystal wallpaper into two 432x257 halves."""
    src = Image.open(REF_DATA / "1989_1280x720.png").convert("RGB")
    # Crop main interior between original top/bottom letterbox bars (y=124..596? No, 1989 has top bar 0..120, content 124..672, bot bar 676..720)
    crystal = src.crop((0, 124, 1280, 672))
    # Build top-left crystal slice + right-side ripple/gold dust slice for 432x514 vertical aspect
    left_hex = crystal.crop((20, 0, 560, 548)).resize((432, 300), Image.Resampling.LANCZOS)
    right_sea = crystal.crop((760, 0, 1280, 548)).resize((432, 240), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (432, 514), (7, 19, 40))
    canvas.paste(left_hex, (0, 34))
    # Blend lower sea crystal smoothly over bottom half
    arr = np.asarray(canvas, dtype=np.float32)
    bot_arr = np.asarray(right_sea, dtype=np.float32)
    y0 = 250
    for dy in range(bot_arr.shape[0]):
        yy = y0 + dy
        if yy >= 514:
            break
        alpha = min(1.0, dy / 54.0)
        arr[yy] = arr[yy] * (1.0 - alpha) + bot_arr[dy] * alpha

    # Darken center band gently for high text contrast over menus/slots
    y_norm = np.linspace(-1.0, 1.0, 514)[:, None, None]
    shade = 0.62 + 0.14 * (y_norm ** 2)
    arr = np.clip(arr * shade, 0, 255).astype(np.uint8)
    full = Image.fromarray(arr, mode="RGB")

    # Add signature GINKA deep navy header/footer bars + crisp #25c4de cyan horizon lines
    draw = ImageDraw.Draw(full)
    draw.rectangle((0, 0, 431, 41), fill=(6, 17, 36))
    draw.rectangle((0, 42, 431, 43), fill=(37, 196, 222))
    draw.rectangle((0, 476, 431, 477), fill=(37, 196, 222))
    draw.rectangle((0, 478, 431, 513), fill=(6, 17, 36))

    full.crop((0, 0, 432, 257)).save(UI_OUT / "panel_top.jpg", format="JPEG", quality=78, optimize=True)
    full.crop((0, 257, 432, 514)).save(UI_OUT / "panel_bot.jpg", format="JPEG", quality=78, optimize=True)


def build_textbox():
    """Build clean GINKA midnight-sea translucent dialogue panel (432x249) with NO top bar."""
    t = np.linspace(0.0, 1.0, 249)[:, None, None]
    rgb = np.array([5.0, 15.0, 34.0]) + t * np.array([5.0, 13.0, 26.0])
    rgb = np.broadcast_to(rgb, (249, 432, 3)).astype(np.float32)
    alpha = 232.0 + t * 18.0
    alpha = np.broadcast_to(alpha, (249, 432, 1)).astype(np.float32)
    rgba = np.concatenate([rgb, alpha], axis=2).clip(0, 255).astype(np.uint8)
    save_quantized_png(Image.fromarray(rgba, mode="RGBA"), UI_OUT / "textbox_bg.png", colors=64)


def build_name_line():
    """Extract GINKA's signature butterfly-on-line speaker divider from data_1981 (396x24)."""
    src = Image.open(REF_DATA / "1981_617x71.png").convert("RGBA")
    # Crop below top curved box border and stop cleanly before right vertical frame stroke
    sub = src.crop((0, 38, 294, 71))
    arr = np.asarray(sub, dtype=np.float32)
    ink = np.clip((255.0 - arr[:, :, :3].mean(axis=2)) / 255.0, 0.0, 1.0) * (arr[:, :, 3] / 255.0)
    out = np.zeros_like(arr)
    out[:, :, 0] = 178.0
    out[:, :, 1] = 236.0
    out[:, :, 2] = 255.0
    out[:, :, 3] = np.clip(ink * 255.0 * 1.25, 0, 255)
    clean = Image.fromarray(out.astype(np.uint8), mode="RGBA").resize((240, 14), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (396, 14), (0, 0, 0, 0))
    canvas.paste(clean, (0, 0), clean)
    save_quantized_png(canvas, UI_OUT / "name_line.png", colors=32)


def build_choice_bars():
    """Extract GINKA's faceted butterfly choice plate from data_1995 (392x60)."""
    src = Image.open(REF_DATA / "1995_768x261.png").convert("RGBA")
    # Row 2 (y=176..261) is midnight-navy to cyan-blue bottom gradient with sharp cyan border & butterflies
    row = src.crop((0, 176, 768, 261)).resize((392, 60), Image.Resampling.LANCZOS)
    arr = np.asarray(row, dtype=np.uint8).copy()
    # Mask off the baked-in top-left "Select" text using clean row-matched interior pixels
    arr[2:19, 4:64] = arr[2:19, 64:65]
    save_quantized_png(Image.fromarray(arr, mode="RGBA"), UI_OUT / "choice_bar.png", colors=96)


def build_header_pill():
    """Create GINKA's iconic cyan faceted section ribbon (388x34)."""
    w, h = 388, 34
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Base rounded pill gradient (#125a82 -> #1da7c9)
    for x in range(w):
        t = x / (w - 1)
        r = int(14 + 18 * t)
        g = int(86 + 86 * t)
        b = int(132 + 74 * t)
        draw.line((x, 2, x, h - 4), fill=(r, g, b, 236))
    # Geometric slanted facets on right (mirroring data_0114 Language Display ribbon)
    draw.polygon([(276, 2), (322, 2), (296, h - 4), (250, h - 4)], fill=(54, 198, 224, 95))
    draw.polygon([(334, 2), (366, 2), (344, h - 4), (312, h - 4)], fill=(120, 228, 246, 75))
    # Crisp luminous bottom white border + top cyan rim
    draw.rectangle((4, h - 4, w - 5, h - 2), fill=(235, 250, 255, 255))
    draw.rectangle((4, 1, w - 5, 2), fill=(88, 218, 240, 230))
    save_quantized_png(im, UI_OUT / "header_pill.png", colors=64)


def build_title_assets():
    """Crop all 3 progressive title CGs to full-bleed 432x514 (split 432x257 top/bot) with zero torii shift."""
    # Fixed 432:514 crop box (605x720) shifted slightly left so GINKA clears the head while keeping character mostly in-frame
    crop_box = (608, 0, 608 + 605, 720)
    banner_sources = {
        "title_bg1": RAW_DATA / "00496.png",
        "title_bg2": REF_DATA / "title_base2.png",
        "title_bg3": REF_DATA / "title_base3.png",
    }
    for old_name in ("title_bg1.jpg", "title_bg2.jpg", "title_bg3.jpg", "title_lower_bg.jpg", "title_copy.png"):
        old_file = UI_OUT / old_name
        if old_file.exists():
            old_file.unlink()

    for prefix, src_path in banner_sources.items():
        full = Image.open(src_path).convert("RGB").crop(crop_box).resize((432, 514), Image.Resampling.LANCZOS)
        full.crop((0, 0, 432, 257)).save(UI_OUT / f"{prefix}_top.jpg", format="JPEG", quality=84, optimize=True)
        full.crop((0, 257, 432, 514)).save(UI_OUT / f"{prefix}_bot.jpg", format="JPEG", quality=84, optimize=True)

    # Crisp white + ocean-navy halo button sprites sliced from patch/0132 (NS0 'off' mask -> no ghosting)
    ns0 = json.loads(TITLE_NS0.read_text(encoding="utf-8"))
    atlas = Image.open(REF_PATCH / "0132_234x250.png").convert("RGBA")
    res = ns0["result"]
    mapping = {
        "cont": "title_btn_cont.png",
        "after": "title_btn_after.png",
        "next": "title_btn_next.png",
        "start": "title_btn_start.png",
        "load": "title_btn_load.png",
        "option": "title_btn_system.png",
        "extra": "title_btn_extra.png",
        "exit": "title_btn_exit.png",
    }
    scale = 1.60
    pad = 4
    for key, out_name in mapping.items():
        info = res[key]["uistates"]["off"]
        cx, cy, cw, ch = info["cx"], info["cy"], info["cw"], info["ch"]
        crop = atlas.crop((cx, cy, cx + cw, cy + ch))
        if info.get("cr", 0):
            crop = crop.transpose(Image.Transpose.ROTATE_270)
        nw = max(1, int(round(crop.width * scale)))
        nh = max(1, int(round(crop.height * scale)))
        resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)
        mask = np.asarray(resized)[:, :, 3]
        w, h = nw + pad * 2, nh + pad * 2

        halo = np.zeros((h, w, 4), dtype=np.uint8)
        halo[pad : pad + nh, pad : pad + nw, 0] = 6
        halo[pad : pad + nh, pad : pad + nw, 1] = 28
        halo[pad : pad + nh, pad : pad + nw, 2] = 62
        halo[pad : pad + nh, pad : pad + nw, 3] = mask
        halo_im = Image.fromarray(halo, "RGBA").filter(ImageFilter.GaussianBlur(radius=1.7))
        ha = np.asarray(halo_im).copy()
        ha[:, :, 3] = np.clip(ha[:, :, 3].astype(np.float32) * 2.2, 0, 235).astype(np.uint8)

        m_pad = np.pad(mask, pad)
        dilated = np.maximum.reduce([
            np.roll(m_pad, 1, axis=0),
            np.roll(m_pad, -1, axis=0),
            np.roll(m_pad, 1, axis=1),
            np.roll(m_pad, -1, axis=1),
            m_pad,
        ])
        rim = np.zeros((h, w, 4), dtype=np.uint8)
        rim[:, :, :3] = [6, 28, 62]
        rim[:, :, 3] = np.clip(dilated.astype(np.float32) * 0.75, 0, 210).astype(np.uint8)

        glyph = np.zeros((h, w, 4), dtype=np.uint8)
        glyph[pad : pad + nh, pad : pad + nw, :3] = [255, 255, 255]
        glyph[pad : pad + nh, pad : pad + nw, 3] = mask

        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.alpha_composite(Image.fromarray(ha, "RGBA"), (1, 1))
        canvas.alpha_composite(Image.fromarray(rim, "RGBA"), (0, 0))
        canvas.alpha_composite(Image.fromarray(glyph, "RGBA"), (0, 0))
        save_quantized_png(canvas, UI_OUT / out_name, colors=48)

    new_info = res["new"]["uistates"]["(~null~)"]
    new_crop = atlas.crop((new_info["cx"], new_info["cy"], new_info["cx"] + new_info["cw"], new_info["cy"] + new_info["ch"]))
    save_quantized_png(new_crop.resize((42, 14), Image.Resampling.LANCZOS), UI_OUT / "title_new.png", colors=32)


def build_app_icon():
    """Crop Ginka's face from the title CG into the 192x192 circular app cover icon."""
    src = Image.open(RAW_DATA / "00496.png").convert("RGBA")
    cx, cy, size = 948, 224, 340
    half = size // 2
    cropped = src.crop((cx - half, cy - half, cx + half, cy + half)).resize((192, 192), Image.Resampling.LANCZOS)
    mask_hi = Image.new("L", (768, 768), 0)
    ImageDraw.Draw(mask_hi).ellipse((4, 4, 764, 764), fill=255)
    mask = mask_hi.resize((192, 192), Image.Resampling.LANCZOS)
    icon = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    icon.paste(cropped, (0, 0), mask)
    icon.save(ROOT / "src" / "common" / "logo.png", format="PNG", optimize=True)
    print(f"BUILT logo.png: {icon.size} {icon.mode} ({(ROOT / 'src' / 'common' / 'logo.png').stat().st_size} bytes)")


def main():
    UI_OUT.mkdir(parents=True, exist_ok=True)
    build_panel_backdrop()
    build_textbox()
    build_name_line()
    build_choice_bars()
    build_header_pill()
    build_title_assets()
    build_app_icon()
    for p in sorted(UI_OUT.iterdir()):
        im = Image.open(p)
        assert im.width <= 432 and im.height <= 286, (p.name, im.size)
        print(f"BUILT {p.name}: {im.size} {im.mode} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
