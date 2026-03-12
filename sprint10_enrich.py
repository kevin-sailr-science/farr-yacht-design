#!/usr/bin/env python3
"""Sprint 10: Data Completeness & Image Pipeline

Enriches boats.json with:
1. Image mapping — links OldFYDWebSite pics to designs missing images
2. LOA inference — parses size from names/descriptions
3. Description generation — creates short descriptions from metadata
4. Featured image expansion — adds OldFYD pics as featured images

Conservative: only fills empty fields, never overwrites existing data.
"""

import json
import os
import re
import shutil
from pathlib import Path
from collections import defaultdict

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
BOATS_JSON = BASE / "_data" / "boats.json"
IMAGES_DIR = BASE / "images"
OLD_PICS = BASE.parent.parent / "OldFYDWebSite" / "wwwroot" / "wwwroot" / "pics"

# ── Load data ──────────────────────────────────────────────────────────────────
with open(BOATS_JSON) as f:
    boats = json.load(f)

# Snapshot before-counts
def coverage(boats_list):
    total = len(boats_list)
    visible = [b for b in boats_list if not b.get("hidden")]
    def s(v): return str(v).strip() if v is not None and v != "" else ""
    def has_loa(b):
        sp = b.get("specs") or {}
        lo = sp.get("loa") or {}
        return bool(lo.get("ft") or lo.get("m"))
    def has_img(b):
        im = b.get("images")
        return isinstance(im, dict) and bool(im.get("main"))
    return {
        "total": total,
        "visible": len(visible),
        "year": sum(1 for b in boats_list if b.get("year")),
        "shortDescription": sum(1 for b in boats_list if s(b.get("shortDescription"))),
        "loa": sum(1 for b in boats_list if has_loa(b)),
        "designType": sum(1 for b in boats_list if s(b.get("designType"))),
        "builder": sum(1 for b in boats_list if s(b.get("builder"))),
        "description": sum(1 for b in boats_list if s(b.get("description"))),
        "images_main": sum(1 for b in boats_list if has_img(b)),
    }

before = coverage(boats)
changes = defaultdict(list)

# ── 0. BUILD DUPLICATE INDEX ───────────────────────────────────────────────────
# Some designs exist as both D.026 (Tier 1) and D.26 (Tier 2). Skip Tier 2
# duplicates for image/description enrichment to avoid double-mapping.
dn_stripped_map = {}
for boat in boats:
    dn = str(boat.get("designNumber", "")).lstrip("0") or "0"
    dn_stripped_map.setdefault(dn, []).append(boat)

tier2_skip = set()
for dn, entries in dn_stripped_map.items():
    if len(entries) > 1:
        # If there's a Tier 1 entry, skip Tier 2 for enrichment
        has_t1 = any(e.get("tier") == 1 for e in entries)
        if has_t1:
            for e in entries:
                if e.get("tier") != 1:
                    tier2_skip.add(id(e))

print(f"Duplicate pairs: {sum(1 for v in dn_stripped_map.values() if len(v) > 1)}")
print(f"Tier 2 entries to skip: {len(tier2_skip)}")

# ── 1. IMAGE MAPPING ──────────────────────────────────────────────────────────
# Index all OldFYD pics by design number
old_pic_index = defaultdict(list)
if OLD_PICS.exists():
    for f in sorted(OLD_PICS.iterdir()):
        if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif'):
            m = re.match(r'^(\d+)', f.name)
            if m:
                old_pic_index[m.group(1)].append(f.name)

# Existing images in www/images (lowercase for matching)
existing_images = {f.lower(): f for f in os.listdir(IMAGES_DIR) if os.path.isfile(IMAGES_DIR / f)}

print(f"Old pics indexed: {sum(len(v) for v in old_pic_index.values())} files across {len(old_pic_index)} design numbers")
print(f"Existing www/images: {len(existing_images)} files")

images_added = 0
featured_added = 0

for boat in boats:
    if boat.get("hidden") or id(boat) in tier2_skip:
        continue

    dn_raw = str(boat.get("designNumber", ""))
    dn_stripped = dn_raw.lstrip("0") or "0"
    dn_padded = dn_stripped.zfill(3)

    # Find matching old pics
    old_files = old_pic_index.get(dn_stripped, []) or old_pic_index.get(dn_padded, [])
    if not old_files:
        continue

    images = boat.get("images")
    if not isinstance(images, dict):
        images = {}
        boat["images"] = images

    # If no main image, pick the best candidate and copy it
    if not images.get("main"):
        # Pick the first _01 file, or just the first file
        best = None
        for of in old_files:
            if "_01" in of or of.startswith(f"{dn_padded}."):
                best = of
                break
        if not best:
            best = old_files[0]

        # Copy to www/images
        src = OLD_PICS / best
        # Normalize filename: lowercase, ensure design number prefix
        dst_name = best.lower()
        dst = IMAGES_DIR / dst_name
        if not dst.exists():
            shutil.copy2(src, dst)

        images["main"] = dst_name
        images_added += 1
        changes["image_main"].append(f"D.{dn_raw}: {dst_name}")

    # Record available featured images from OldFYD (metadata only — don't copy files)
    # build_site.py doesn't use featured images yet, so no need to bloat the repo
    current_featured = images.get("featured", [])
    current_featured_lower = {f.lower() for f in current_featured}
    current_main_lower = (images.get("main") or "").lower()

    new_featured = []
    for of in old_files:
        of_lower = of.lower()
        if of_lower == current_main_lower:
            continue
        if of_lower in current_featured_lower:
            continue
        new_featured.append(of_lower)

    if new_featured:
        images["featured"] = current_featured + new_featured
        featured_added += len(new_featured)
        changes["image_featured"].append(f"D.{dn_raw}: +{len(new_featured)} available")

print(f"\nImages: {images_added} new main images, {featured_added} new featured images")

# ── 2. LOA INFERENCE ──────────────────────────────────────────────────────────
# Parse size from name/shortDescription
loa_patterns = [
    (r"(\d+(?:\.\d+)?)\s*(?:ft|foot|feet|')", "ft"),
    (r"(\d+(?:\.\d+)?)\s*(?:m\b|metre|meter|M\b)", "m"),
]

loa_added = 0
for boat in boats:
    if boat.get("hidden"):
        continue
    specs = boat.get("specs") or {}
    boat["specs"] = specs
    loa = specs.get("loa") or {}
    if loa.get("ft") or loa.get("m"):
        continue  # already has LOA

    text = f"{boat.get('name', '')} {boat.get('shortDescription', '')} {boat.get('shortSummary', '')}"

    for pat, unit in loa_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if unit == "ft" and 5 <= val <= 300:
                specs["loa"] = {"m": round(val * 0.3048, 2), "ft": val}
                loa_added += 1
                changes["loa"].append(f"D.{boat['designNumber']}: {val}ft from text")
                break
            elif unit == "m" and 2 <= val <= 100:
                specs["loa"] = {"m": val, "ft": round(val / 0.3048, 1)}
                loa_added += 1
                changes["loa"].append(f"D.{boat['designNumber']}: {val}m from text")
                break

print(f"LOA: {loa_added} values inferred from names/descriptions")

# ── 3. DESCRIPTION GENERATION ─────────────────────────────────────────────────
# For designs with no description, generate a factual summary from metadata
desc_added = 0
for boat in boats:
    if boat.get("hidden"):
        continue
    existing_desc = boat.get("description")
    if existing_desc and str(existing_desc).strip():
        continue  # already has description

    dn = boat.get("designNumber", "?")
    name = boat.get("name", "")
    year = boat.get("year")
    dtype = boat.get("designType", "")
    builder = boat.get("builder", "")
    specs = boat.get("specs") or {}
    loa = specs.get("loa") or {}
    loa_ft = loa.get("ft")
    loa_m = loa.get("m")
    short_desc = boat.get("shortDescription", "")

    parts = []

    # Opening line
    if name and dtype and year:
        parts.append(f"Design {dn}, {name}, is a {dtype.lower()} designed by Farr Yacht Design in {year}.")
    elif name and year:
        parts.append(f"Design {dn}, {name}, was designed by Farr Yacht Design in {year}.")
    elif dtype and year:
        parts.append(f"Design {dn} is a {dtype.lower()} designed by Farr Yacht Design in {year}.")
    elif year:
        parts.append(f"Design {dn} was created by Farr Yacht Design in {year}.")
    else:
        continue  # Not enough data to generate anything useful

    # Size
    if loa_ft and loa_m:
        parts.append(f"She has an overall length of {loa_ft:.0f} feet ({loa_m:.1f}m).")
    elif loa_ft:
        parts.append(f"She has an overall length of {loa_ft:.0f} feet.")
    elif loa_m:
        parts.append(f"She has an overall length of {loa_m:.1f} metres.")

    # Builder
    if builder:
        parts.append(f"Built by {builder}.")

    desc = " ".join(parts)
    if len(desc) > 40:  # Only if we generated something meaningful
        boat["description"] = desc
        desc_added += 1
        if desc_added <= 5:
            changes["description_sample"].append(f"D.{dn}: {desc[:100]}...")

print(f"Descriptions: {desc_added} generated from metadata")

# ── 4. SHORT DESCRIPTION GAP-FILL ─────────────────────────────────────────────
# Fill missing shortDescription from name + type
short_added = 0
for boat in boats:
    if boat.get("hidden"):
        continue
    existing_short = boat.get("shortDescription")
    if existing_short and str(existing_short).strip():
        continue

    name = boat.get("name", "")
    dtype = boat.get("designType", "")

    if name:
        boat["shortDescription"] = name
        short_added += 1

print(f"Short descriptions: {short_added} filled from name")

# ── SAVE ───────────────────────────────────────────────────────────────────────
with open(BOATS_JSON, "w") as f:
    json.dump(boats, f, indent=2, ensure_ascii=False)
    f.write("\n")

# ── COVERAGE REPORT ────────────────────────────────────────────────────────────
after = coverage(boats)

print("\n" + "=" * 60)
print("COVERAGE REPORT — Before vs After")
print("=" * 60)
fields = ["year", "shortDescription", "loa", "designType", "builder", "description", "images_main"]
labels = ["Year", "Short Description", "LOA", "Design Type", "Builder", "Description", "Images (main)"]

for field, label in zip(fields, labels):
    b = before[field]
    a = after[field]
    delta = a - b
    total = before["total"]
    arrow = f"+{delta}" if delta > 0 else str(delta)
    print(f"  {label:20s}  {b:4d} → {a:4d}  ({arrow:>4s})  {100*a//total}%")

print(f"\n  Total designs: {after['total']}  Visible: {after['visible']}")

# ── CHANGE LOG ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("CHANGE DETAILS")
print("=" * 60)
for category, items in changes.items():
    print(f"\n{category} ({len(items)}):")
    for item in items[:10]:
        print(f"  {item}")
    if len(items) > 10:
        print(f"  ... and {len(items) - 10} more")

print("\nDone! boats.json updated.")
