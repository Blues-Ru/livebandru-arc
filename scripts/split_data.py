#!/usr/bin/env python3
"""
One-time script: split monolithic YAML data files into per-entity files.

  liveband-data/bands.yaml  → data/bands/{slug}.yaml
  liveband-data/clubs.yaml  → data/clubs/{slug}.yaml
  liveband-data/cities.yaml → data/cities/{slug}.yaml
  liveband-data/genres.yaml → data/genres/{slug}.yaml
  liveband-data/gigs.yaml   → data/gigs/{club-slug}/{year}.yaml
                               data/gigs/_misc/{year}.yaml  (no club)

Cleaning applied to every record:
  - Computed/denormalized fields are stripped (regenerated at build time).
  - Keys with null, [], or {} values are omitted.
"""

import yaml
from pathlib import Path
from collections import defaultdict

ARC  = Path(__file__).parent.parent
DATA = ARC / "data"
# Monolithic source (liveband-data/) — read-only ETL output
SRC  = ARC.parent / "liveband-data"

# Fields that are derived/computed at generation time — never store in YAML
STRIP = {
    "bands":  {"gig_count", "gig_years",
                "city_name", "city_token",
                "genre_name", "genre_token",
                "secondary_genre_name", "secondary_genre_token"},
    "clubs":  {"gig_count", "gig_years", "city_name", "city_token"},
    "cities": {"band_count", "club_count"},
    "genres": {"band_count"},
    "gigs":   {"city_name"},
}


def clean(record: dict, strip_keys: set) -> dict:
    """Remove computed keys and recursively drop null / empty collections."""
    out = {}
    for k, v in record.items():
        if k in strip_keys:
            continue
        v = _clean_value(v)
        if v is not None:
            out[k] = v
    return out


def _clean_value(v):
    if isinstance(v, dict):
        cleaned = {k2: _clean_value(v2) for k2, v2 in v.items()}
        cleaned = {k2: v2 for k2, v2 in cleaned.items() if v2 is not None}
        return cleaned or None
    if isinstance(v, list):
        cleaned = [_clean_value(i) for i in v]
        cleaned = [i for i in cleaned if i is not None]
        return cleaned or None
    return v  # None passthrough stripped by caller


def write_yaml(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(obj, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False)


def split_entities(name: str, key: str = "token"):
    src = SRC / f"{name}.yaml"
    items = yaml.safe_load(src.read_text(encoding="utf-8"))
    strip_keys = STRIP.get(name, set())
    out_dir = DATA / name
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for item in items:
        slug = item[key]
        if slug in seen:
            slug = f"{slug}-{item['id']}"
        seen.add(slug)
        write_yaml(out_dir / f"{slug}.yaml", clean(item, strip_keys))
    print(f"  {name}: {len(items)} files → data/{name}/")


def split_gigs():
    src = SRC / "gigs.yaml"
    gigs = yaml.safe_load(src.read_text(encoding="utf-8"))
    strip_keys = STRIP["gigs"]

    buckets: dict[tuple, list] = defaultdict(list)
    for g in gigs:
        club = g.get("club_token") or "_misc"
        year = str(g["date"])[:4]
        buckets[(club, year)].append(clean(g, strip_keys))

    count = 0
    for (club, year), items in sorted(buckets.items()):
        write_yaml(DATA / "gigs" / club / f"{year}.yaml", items)
        count += 1

    print(f"  gigs: {len(gigs)} gigs → {count} files in data/gigs/")


if __name__ == "__main__":
    import shutil
    print("Splitting data files...")
    for name in ("bands", "clubs", "cities", "genres"):
        d = DATA / name
        if d.exists():
            shutil.rmtree(d)
    if (DATA / "gigs").exists():
        shutil.rmtree(DATA / "gigs")

    split_entities("bands")
    split_entities("clubs")
    split_entities("cities")
    split_entities("genres")
    split_gigs()
    print("Done.")
