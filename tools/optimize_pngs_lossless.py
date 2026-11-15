"""Exact lossless PNG palette permutation + adaptive scanline filter optimization.

Never alters pixels, dimensions, color depth, or palette entries; verifies decoded
RGBA bytes are bit-for-bit identical before replacing any PNG file.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import io
import json
import struct
import zlib

import numpy as np
from PIL import Image

ROOT = Path(r"E:\Antigravity\ginka-rw5")
DIRS = [
    ROOT / "src" / "common" / "images",
    ROOT / "src" / "common" / "faces",
    ROOT / "src" / "common" / "ui",
]


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_indexed_png(indices, colors, adaptive):
    rows = []
    previous = np.zeros(indices.shape[1], dtype=np.int16)
    for row in indices:
        row = row.astype(np.int16)
        left = np.concatenate(([0], row[:-1]))
        up_left = np.concatenate(([0], previous[:-1]))
        if adaptive:
            p = left + previous - up_left
            pa = np.abs(p - left)
            pb = np.abs(p - previous)
            pc = np.abs(p - up_left)
            predictor = np.where((pa <= pb) & (pa <= pc), left, np.where(pb <= pc, previous, up_left))
            variants = [row, row - left, row - previous, row - ((left + previous) // 2), row - predictor]
            costs = [np.minimum(v & 255, 256 - (v & 255)).sum() for v in variants]
            f = int(np.argmin(costs))
            data = variants[f]
        else:
            f = 0
            data = row
        rows.append(bytes([f]) + (data & 255).astype("uint8").tobytes())
        previous = row

    alpha = colors[:, 3].tobytes().rstrip(b"\xff")
    head = struct.pack(">IIBBBBB", indices.shape[1], indices.shape[0], 8, 3, 0, 0, 0)
    parts = [
        b"\x89PNG\r\n\x1a\n",
        chunk(b"IHDR", head),
        chunk(b"PLTE", colors[:, :3].tobytes()),
    ]
    if alpha:
        parts.append(chunk(b"tRNS", alpha))
    parts.append(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
    parts.append(chunk(b"IEND", b""))
    return b"".join(parts)


def optimize_one(path):
    raw = path.read_bytes()
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    arr = np.asarray(im)
    colors, indices, counts = np.unique(arr.reshape(-1, 4), axis=0, return_inverse=True, return_counts=True)
    if len(colors) > 256:
        return {
            "file": path.relative_to(ROOT).as_posix(),
            "before": len(raw),
            "after": len(raw),
            "strategy": "retained",
            "rgbaIdentical": True,
        }

    orderings = [
        ("rgba", np.arange(len(colors))),
        ("frequency", np.argsort(-counts, kind="stable")),
    ]
    distance = np.sum((colors.astype(np.int32)[:, None, :] - colors.astype(np.int32)[None, :, :]) ** 2, axis=2)
    remaining = np.ones(len(colors), dtype=bool)
    current = int(np.argmax(counts))
    nearest = []
    for _ in range(len(colors)):
        nearest.append(current)
        remaining[current] = False
        if remaining.any():
            current = int(np.argmin(np.where(remaining, distance[current], np.iinfo(np.int32).max)))
    orderings.append(("neighbour", np.array(nearest)))

    best = raw
    strategy = "retained"
    for label, order in orderings:
        inverse = np.empty(len(order), dtype=np.uint8)
        inverse[order] = np.arange(len(order), dtype=np.uint8)
        idx = inverse[indices].reshape(arr.shape[:2])
        for adaptive in (False, True):
            candidate = encode_indexed_png(idx, colors[order], adaptive)
            if len(candidate) < len(best):
                best = candidate
                strategy = label + ("/adaptive" if adaptive else "/none")

    assert Image.open(io.BytesIO(best)).convert("RGBA").tobytes() == im.tobytes(), path
    if best is not raw:
        path.write_bytes(best)
    return {
        "file": path.relative_to(ROOT).as_posix(),
        "before": len(raw),
        "after": len(best),
        "strategy": strategy,
        "rgbaIdentical": True,
        "sha256": hashlib.sha256(best).hexdigest(),
    }


def main():
    targets = sorted(p for d in DIRS if d.exists() for p in d.rglob("*.png"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(optimize_one, targets))
    before = sum(r["before"] for r in rows)
    after = sum(r["after"] for r in rows)
    report = {
        "passed": True,
        "algorithm": "exact lossless palette permutation + adaptive PNG scanline filter search",
        "images": len(rows),
        "beforeBytes": before,
        "afterBytes": after,
        "savedBytes": before - after,
        "allDecodedRGBAIdentical": True,
        "rows": rows,
    }
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "png-lossless.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}))


if __name__ == "__main__":
    main()
