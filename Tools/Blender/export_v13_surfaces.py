"""Export the unchanged v12/v13 driving layout without opening or changing the .blend.

Run with Blender's bundled Python (it supplies numpy):
  python3.13 export_v13_surfaces.py /path/to/Blender-project /path/to/output.json
The dense river stations/curvature come from the same generator that carved Ground.
"""
import importlib.util
import json
from pathlib import Path
import re
import sys


def export(source, destination):
    source = Path(source)
    script = source / "ArtPass_v13/scripts/rg_layout12.py"
    spec = importlib.util.spec_from_file_location("roadgame_v13_layout", script)
    layout = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(layout)
    river = layout.River(0.5)
    original = json.loads((source / "ArtPass_v12/data/river_v12.json").read_text())
    stations = []
    # Keep two neighbouring stations past the bounds for accurate nearest-segment queries.
    # Further scenery-only water must not alter the later procedural zones.
    for i, (p, attr, curvature) in enumerate(zip(river.P, river.A, river.curv)):
        if not (-130 <= p[0] <= 130 and -130 <= p[1] <= 112):
            continue
        stations.append(dict(x=round(float(p[0]), 6), z=round(float(p[1]), 6),
                             w=round(float(attr[0]), 6), b=round(float(attr[1]), 6),
                             d=round(float(attr[2]), 6), k=round(float(curvature), 9)))
    bridges = []
    for bridge in original["bridges"]:
        samples = [dict(x=s["p"][0], y=s["p"][1], z=s["p"][2], halfWidth=s["half_width"])
                   for s in bridge["deck"]]
        bridges.append(dict(name=bridge["name"], rampLength=bridge["ramp_length"],
                            totalLength=bridge["total_length"], samples=samples))
    moved = []
    for item in original["moved_spawns"]:
        match = re.match(r"Spawn_(\d+)_", item["object"])
        if not match:
            raise ValueError(f"Unknown spawn name: {item['object']}")
        x, y, z = item["unity_to"]
        moved.append(dict(id=int(match[1]), x=x, y=y, z=z))
    result = dict(source="DustFlats_Level_v13_SmoothPass.blend; v12 river layout unchanged",
                  waterLevel=original["water_level_y"], stations=stations,
                  outline=[dict(x=p[0], z=p[2]) for p in original["outline_inner_edge"]],
                  bridges=bridges, movedSpawns=moved)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(f"Exported {len(stations)} river stations, {len(bridges)} bridges, "
          f"{len(result['outline'])} outline points, {len(moved)} moved spawns: {destination}")


if __name__ == "__main__":
    export(sys.argv[1], sys.argv[2])
