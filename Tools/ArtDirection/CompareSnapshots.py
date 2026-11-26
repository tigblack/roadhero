#!/usr/bin/env python3
"""Compare exported Unity pose/HUD snapshots without session-specific object IDs.

Export only comparable state: camera pose/projection/viewport; transforms keyed by
stable hierarchy path; HUD text, rects, scale, color and active state; HP/action
values. Lists of objects with unique ``path`` fields are matched by path rather
than Unity enumeration order. Keep style/material/light changes outside this data.

Example:
    python3 Tools/ArtDirection/CompareSnapshots.py reference.json archero2.json

The original five screenshots have no exported pose/HUD JSON. Their EntityID hash
cannot serve as a cross-session reference. A manifest-derived reference can check
the known camera/player/boss fields; --allow-extra explicitly permits that subset.
This tool does not infer an old snapshot from pixels or certify unknown state.
"""

import argparse
import json
import math
import sys
from pathlib import Path


IGNORED_KEYS = {"entityId", "instanceId", "sessionId", "fingerprint", "captureUtc"}


def normalize(value, ignored):
    if isinstance(value, dict):
        return {key: normalize(item, ignored) for key, item in sorted(value.items()) if key not in ignored}
    if isinstance(value, list):
        if value and all(isinstance(item, dict) and isinstance(item.get("path"), str) for item in value):
            paths = [item["path"] for item in value]
            if len(set(paths)) != len(paths):
                raise ValueError("Snapshot has duplicate hierarchy paths; include a stable same-name sibling ordinal.")
            return {item["path"]: normalize({key: part for key, part in item.items() if key != "path"}, ignored)
                    for item in sorted(value, key=lambda item: item["path"])}
        return [normalize(item, ignored) for item in value]
    return value


def compare(expected, actual, path, tolerance, allow_extra, differences, counts):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            differences.append(f"{path}: expected object, got {type(actual).__name__}")
            return
        for key, value in expected.items():
            if key not in actual:
                differences.append(f"{path}/{key}: missing")
            else:
                compare(value, actual[key], f"{path}/{key}", tolerance, allow_extra, differences, counts)
        if not allow_extra:
            differences.extend(f"{path}/{key}: unexpected" for key in sorted(actual.keys() - expected.keys()))
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            differences.append(f"{path}: expected list, got {type(actual).__name__}")
            return
        if len(expected) != len(actual):
            differences.append(f"{path}: list length {len(actual)} differs from {len(expected)}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            compare(left, right, f"{path}/{index}", tolerance, allow_extra, differences, counts)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        counts[0] += 1
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            differences.append(f"{path}: expected number {expected!r}, got {actual!r}")
        elif not math.isfinite(expected) or not math.isfinite(actual) or abs(expected - actual) > tolerance:
            differences.append(f"{path}: {actual!r} differs from {expected!r} (tolerance {tolerance:g})")
    else:
        counts[0] += 1
        if type(actual) is not type(expected) or actual != expected:
            differences.append(f"{path}: {actual!r} differs from {expected!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reference", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-5, help="Absolute numeric tolerance, default 1e-5.")
    parser.add_argument("--ignore-key", action="append", default=[], help="Additional volatile key to omit at every level.")
    parser.add_argument("--allow-extra", action="store_true", help="Check an explicitly partial reference; permit additional actual fields.")
    parser.add_argument("--max-differences", type=int, default=30)
    args = parser.parse_args()
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        parser.error("tolerance must be finite and nonnegative")
    try:
        ignored = IGNORED_KEYS | set(args.ignore_key)
        reference = normalize(json.loads(args.reference.read_text()), ignored)
        actual = normalize(json.loads(args.actual.read_text()), ignored)
        differences, counts = [], [0]
        compare(reference, actual, "$", args.tolerance, args.allow_extra, differences, counts)
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if not counts[0] and not differences:
        print("ERROR: no comparable values in the reference", file=sys.stderr)
        return 2
    if differences:
        print(f"FAIL: {len(differences)} differences across {counts[0]} compared values.")
        for difference in differences[:max(0, args.max_differences)]:
            print(difference)
        return 1
    scope = "explicit reference subset" if args.allow_extra else "complete exported snapshot"
    print(f"PASS: {counts[0]} values match ({scope}, absolute tolerance {args.tolerance:g}); session IDs excluded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
