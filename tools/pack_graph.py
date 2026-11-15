"""Bundle converted/graph.json and image-map.json into compact ES modules for QuickApp."""
from pathlib import Path
import json

ROOT = Path(r"E:\Antigravity\ginka-rw5")
CONV = ROOT / "converted"
COMMON = ROOT / "src" / "common"


def compact_path(uri):
    if uri.startswith("/common/images/"):
        return "~" + uri[len("/common/images/"):]
    if uri.startswith("/common/faces/"):
        return "^" + uri[len("/common/faces/"):]
    return uri


def main():
    graph = json.loads((CONV / "graph.json").read_text("utf-8"))
    image_map = json.loads((CONV / "image-map.json").read_text("utf-8"))

    # Keep only the fields needed at runtime and strip repeated URI prefixes to minimize JS bundle size
    compact_assets = {}
    for aid, meta in image_map.items():
        src = compact_path(meta["src"])
        if meta.get("portrait"):
            row = [src, meta["width"], meta["height"]]
            if meta.get("patch"):
                row.extend([compact_path(meta["patch"]), meta["patchRect"], meta["patchAtlas"]])
            compact_assets[aid] = row
        else:
            compact_assets[aid] = [src, meta["width"], meta["height"]]

    graph_js = "export const graph=" + json.dumps(graph, ensure_ascii=False, separators=(",", ":")) + ";\n"
    assets_js = "export const assets=" + json.dumps(compact_assets, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (COMMON / "graph.js").write_text(graph_js, "utf-8")
    (COMMON / "assets.js").write_text(assets_js, "utf-8")
    print(json.dumps({
        "graphBytes": len(graph_js.encode("utf-8")),
        "assetsBytes": len(assets_js.encode("utf-8")),
        "assetCount": len(compact_assets),
    }))


if __name__ == "__main__":
    main()
