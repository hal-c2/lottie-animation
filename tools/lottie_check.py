"""Validate the committed animations without a GUI.

    python tools/lottie_check.py check [ROOT]   every rule below, one line per broken rule
    python tools/lottie_check.py frames [ROOT]  "<file>\t<ip>\t<op>" per Lottie JSON, for the Qt load test

An animation is a stem such as version2/hal-c2-dance; it is complete when it
has <stem>.json, <stem>.lottie, <stem>.blend and <stem>-preview.gif.
"""

import json
import sys
import zipfile
from pathlib import Path

# What the README promises about every animation.
FRAME_RATE = 24
SIZE = 512
PARTS = (".json", ".lottie", ".blend", "-preview.gif")
# Blender writes either a plain or a zstd-compressed .blend.
BLEND_MAGIC = (b"BLENDER", b"\x28\xb5\x2f\xfd")
GIF_MAGIC = (b"GIF87a", b"GIF89a")


def stems(root):
    found = set()
    for version in sorted(root.glob("version*/")):
        for f in version.iterdir():
            for part in PARTS:
                if f.name.endswith(part):
                    found.add(f.parent / f.name[: -len(part)])
    return sorted(found)


def check_json(path, rel, errors):
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        errors.append(f"{rel}: not valid JSON ({e})")
        return None
    if not isinstance(doc, dict):
        errors.append(f"{rel}: the top level is not a JSON object")
        return None
    if not isinstance(doc.get("v"), str) or not doc["v"]:
        errors.append(f"{rel}: no Lottie version string in \"v\"")
    if doc.get("fr") != FRAME_RATE:
        errors.append(f"{rel}: \"fr\" is {doc.get('fr')!r}, expected {FRAME_RATE}")
    for key in ("w", "h"):
        if doc.get(key) != SIZE:
            errors.append(f"{rel}: \"{key}\" is {doc.get(key)!r}, expected {SIZE}")
    ip, op = doc.get("ip"), doc.get("op")
    numbers = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (ip, op))
    if not numbers or not ip < op:
        errors.append(f"{rel}: \"ip\" ({ip!r}) must be a number below \"op\" ({op!r})")
    if not isinstance(doc.get("layers"), list) or not doc["layers"]:
        errors.append(f"{rel}: \"layers\" is missing or empty")
    return doc


def check_lottie(path, rel, sibling, errors):
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        errors.append(f"{rel}: not a zip archive ({e})")
        return
    with archive:
        names = set(archive.namelist())
        if "manifest.json" not in names:
            errors.append(f"{rel}: no manifest.json in the archive")
            return
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            errors.append(f"{rel}: manifest.json is not valid JSON ({e})")
            return
        animations = manifest.get("animations") if isinstance(manifest, dict) else None
        ids = [a.get("id") for a in animations or [] if isinstance(a, dict)]
        if not ids or not all(isinstance(i, str) and i for i in ids):
            errors.append(f"{rel}: manifest.json names no animation (\"animations\": [{{\"id\": …}}])")
            return
        for i in ids:
            if f"animations/{i}.json" not in names:
                errors.append(f"{rel}: manifest.json names \"{i}\" but animations/{i}.json is not in the archive")
        first = f"animations/{ids[0]}.json"
        if first not in names or sibling is None:
            return
        try:
            packed = json.loads(archive.read(first))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            errors.append(f"{rel}: {first} is not valid JSON ({e})")
            return
        if packed != sibling:
            errors.append(f"{rel}: {first} differs from {rel[: -len('.lottie')]}.json; re-export both together")


def check_magic(path, rel, magics, what, errors):
    with path.open("rb") as f:
        head = f.read(8)
    if not head.startswith(magics):
        errors.append(f"{rel}: not a {what} file")


def check(root):
    errors = []
    found = stems(root)
    if not found:
        errors.append(f"{root}: no animations under version*/")
    for stem in found:
        rel = stem.relative_to(root).as_posix()
        missing = [p for p in PARTS if not Path(f"{stem}{p}").is_file()]
        for part in missing:
            errors.append(f"{rel}{part}: missing; every animation has {', '.join(PARTS)}")
        doc = None
        if ".json" not in missing:
            doc = check_json(Path(f"{stem}.json"), f"{rel}.json", errors)
        if ".lottie" not in missing:
            check_lottie(Path(f"{stem}.lottie"), f"{rel}.lottie", doc, errors)
        if ".blend" not in missing:
            check_magic(Path(f"{stem}.blend"), f"{rel}.blend", BLEND_MAGIC, "Blender", errors)
        if "-preview.gif" not in missing:
            check_magic(Path(f"{stem}-preview.gif"), f"{rel}-preview.gif", GIF_MAGIC, "GIF", errors)
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        print(f"check: {len(errors)} problem(s) in {len(found)} animation(s)", file=sys.stderr)
        return 1
    for stem in found:
        print(f"ok {stem.relative_to(root).as_posix()}")
    print(f"check: {len(found)} animation(s) valid")
    return 0


def frames(root):
    for stem in stems(root):
        doc = json.loads(Path(f"{stem}.json").read_text(encoding="utf-8"))
        print(f"{stem}.json\t{doc['ip']}\t{doc['op']}")
    return 0


def main(argv):
    if len(argv) not in (2, 3) or argv[1] not in ("check", "frames"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    root = Path(argv[2] if len(argv) == 3 else Path(__file__).resolve().parent.parent).resolve()
    return {"check": check, "frames": frames}[argv[1]](root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
