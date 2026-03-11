#!/usr/bin/env python3
"""
merge_muse.py — Sprint 7: Merge MUSE extracted data into boats.json

Conservative merge: only fills empty/null fields, never overwrites existing data.
Run extract_muse.py first to generate muse_extracted.json.
"""

import json
import re
import copy
import os

BOATS_JSON = "_data/boats.json"
MUSE_JSON = "muse_extracted.json"
OUTPUT_JSON = "_data/boats.json"  # Overwrite in place
BACKUP_JSON = "_data/boats.json.bak"

# Design list entries that are just contact prompts, not real descriptions
BAD_DESCRIPTIONS = [
    "Contact info@farrdesign.com",
    "Sign up for our email list",
]

# Spec values that are clearly bad parses
BAD_SPEC_VALUES = ["DOWNLOADS", "XX"]


def is_empty(value):
    """Check if a value is empty/null."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, dict) and not any(v for v in value.values() if v is not None):
        return True
    return False


def clean_description(desc):
    """Clean up description text — remove photo credits, contact prompts."""
    if not desc:
        return None

    # Remove photo credit lines
    lines = desc.split('\n\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip photo credits
        if line.startswith('Photo:') or line.startswith('©'):
            continue
        # Skip contact prompts
        if any(bad in line for bad in BAD_DESCRIPTIONS):
            continue
        cleaned.append(line)

    result = '\n\n'.join(cleaned).strip()
    return result if len(result) > 30 else None


def has_bad_value(spec_entry):
    """Check if a spec entry has a clearly bad parsed value."""
    raw = spec_entry.get("raw", "")
    return any(bad in raw for bad in BAD_SPEC_VALUES)


def merge_specs(existing_specs, muse_specs):
    """Merge MUSE specs into existing spec structure."""
    if existing_specs is None:
        existing_specs = {}

    changes = []

    for label, muse_val in muse_specs.items():
        if has_bad_value(muse_val):
            continue

        # Map MUSE labels to boats.json spec structure
        if label == 'loa':
            loa = existing_specs.get('loa') or {}
            if muse_val.get('m') and not loa.get('m'):
                if 'loa' not in existing_specs:
                    existing_specs['loa'] = {}
                existing_specs['loa']['m'] = muse_val['m']
                changes.append(f"loa.m = {muse_val['m']}")
            if muse_val.get('ft') and not loa.get('ft'):
                if 'loa' not in existing_specs:
                    existing_specs['loa'] = {}
                existing_specs['loa']['ft'] = muse_val['ft']
                changes.append(f"loa.ft = {muse_val['ft']}")

        elif label in ('lwl', 'dwl'):
            key = label
            existing_val = existing_specs.get(key) or {}
            if not existing_val:
                existing_specs[key] = {}
            if muse_val.get('m') and not existing_val.get('m'):
                existing_specs[key]['m'] = muse_val['m']
                changes.append(f"{key}.m = {muse_val['m']}")
            if muse_val.get('ft') and not existing_val.get('ft'):
                existing_specs[key]['ft'] = muse_val['ft']
                changes.append(f"{key}.ft = {muse_val['ft']}")

        elif label == 'beam':
            beam = existing_specs.get('beam') or {}
            if not beam:
                existing_specs['beam'] = {}
            if muse_val.get('m') and not beam.get('m'):
                existing_specs['beam']['m'] = muse_val['m']
                changes.append(f"beam.m = {muse_val['m']}")
            if muse_val.get('ft') and not beam.get('ft'):
                existing_specs['beam']['ft'] = muse_val['ft']
                changes.append(f"beam.ft = {muse_val['ft']}")

        elif 'draft' in label:
            # Handle various draft types: "draft", "draft (keel down)", "draft (keel up)", "draft — fixed"
            if 'keel down' in label or 'fixed' in label or label == 'draft':
                key = 'draft'
            elif 'keel up' in label:
                key = 'draftUp'
            else:
                key = 'draft'

            existing_val = existing_specs.get(key) or {}
            if not existing_val:
                existing_specs[key] = {}
            if muse_val.get('m') and not existing_val.get('m'):
                existing_specs[key]['m'] = muse_val['m']
                changes.append(f"{key}.m = {muse_val['m']}")
            if muse_val.get('ft') and not existing_val.get('ft'):
                existing_specs[key]['ft'] = muse_val['ft']
                changes.append(f"{key}.ft = {muse_val['ft']}")

        elif label == 'displacement':
            disp = existing_specs.get('displacement') or {}
            if not disp:
                existing_specs['displacement'] = {}
            if muse_val.get('kg') and not disp.get('kg'):
                existing_specs['displacement']['kg'] = muse_val['kg']
                changes.append(f"displacement.kg = {muse_val['kg']}")
            if muse_val.get('lbs') and not disp.get('lbs'):
                existing_specs['displacement']['lbs'] = muse_val['lbs']
                changes.append(f"displacement.lbs = {muse_val['lbs']}")
            if muse_val.get('tons') and not disp.get('tons'):
                existing_specs['displacement']['tons'] = muse_val['tons']
                changes.append(f"displacement.tons = {muse_val['tons']}")

        elif label == 'ballast':
            ballast = existing_specs.get('ballast') or {}
            if not ballast:
                existing_specs['ballast'] = {}
            if muse_val.get('kg') and not ballast.get('kg'):
                existing_specs['ballast']['kg'] = muse_val['kg']
                changes.append(f"ballast.kg = {muse_val['kg']}")
            if muse_val.get('lbs') and not ballast.get('lbs'):
                existing_specs['ballast']['lbs'] = muse_val['lbs']
                changes.append(f"ballast.lbs = {muse_val['lbs']}")
            if muse_val.get('tons') and not ballast.get('tons'):
                existing_specs['ballast']['tons'] = muse_val['tons']
                changes.append(f"ballast.tons = {muse_val['tons']}")

    return existing_specs, changes


def create_new_design(entry, size_ft=None):
    """Create a new boats.json entry from a design list entry."""
    design_type = entry.get('type', '')

    # Infer designType from type description
    dt = None
    if design_type:
        dl = design_type.lower()
        if any(w in dl for w in ['racer', 'racing', 'od', 'one design', 'ton']):
            dt = 'Racing Yacht'
        elif any(w in dl for w in ['cruiser', 'cruising', 'c/r']):
            dt = 'Cruising Yacht'
        elif 'power' in dl:
            dt = 'Power Yacht'
        elif 'paddleboard' in dl:
            dt = 'Other'
        elif 'centerboard' in dl or 'javelin' in dl or 'cherub' in dl or 'moth' in dl:
            dt = 'Dinghy'
        elif 'charter' in dl:
            dt = 'Cruising Yacht'

    # Extract LOA from type description if not in size data
    loa_ft = size_ft
    if not loa_ft and design_type:
        m = re.match(r"(\d+(?:\.\d+)?)['\s]*(?:ft|')", design_type)
        if m:
            loa_ft = float(m.group(1))

    specs = {}
    if loa_ft:
        specs['loa'] = {'m': None, 'ft': loa_ft}

    return {
        "title": entry['designNumber'],
        "slug": entry['designNumber'],
        "designNumber": entry['designNumber'],
        "name": entry.get('name'),
        "year": entry.get('year'),
        "category": [],
        "classification": None,
        "designRule": None,
        "designType": dt,
        "specs": specs if specs else None,
        "description": None,
        "shortDescription": design_type,
        "shortSummary": None,
        "builder": None,
        "owner": None,
        "rigType": None,
        "rigMaterial": None,
        "keelType": None,
        "hullConstruction": None,
        "hullsBuilt": None,
        "inProduction": None,
        "isArchived": None,
        "images": None,
        "drawings": None,
        "vppFile": None,
        "drupalAlias": None,
        "tier": 2,  # Card-only equivalent — from MUSE list only
        "planStatus": "coming_soon",
        "hasCardPDF": False,
        "cardDrawingCount": None,
        "cardDrawingsAvailable": None,
        "hidden": False,
    }


def main():
    print("=" * 60)
    print("MUSE Data Merge — Sprint 7")
    print("=" * 60)

    # Load data
    with open(BOATS_JSON) as f:
        boats = json.load(f)
    with open(MUSE_JSON) as f:
        muse = json.load(f)

    # Create backup
    with open(BACKUP_JSON, 'w') as f:
        json.dump(boats, f, indent=2, ensure_ascii=False)
    print(f"Backup saved to {BACKUP_JSON}")

    # Index by designNumber
    boats_idx = {}
    for i, b in enumerate(boats):
        dn = str(b.get('designNumber', ''))
        boats_idx[dn] = i

    changes_log = []

    # ── Merge design page data ──
    print(f"\n{'─' * 40}")
    print("Merging design page data...")

    for dp in muse['design_pages']:
        dn = dp['designNumber']
        if dn not in boats_idx:
            print(f"  D.{dn}: NOT IN BOATS.JSON — skipping")
            continue

        idx = boats_idx[dn]
        boat = boats[idx]
        boat_changes = []

        # Merge description
        desc = clean_description(dp.get('description'))
        if desc and is_empty(boat.get('description')):
            boat['description'] = desc
            boat_changes.append(f"description ({len(desc)} chars)")

        # Merge specs
        if dp.get('specs'):
            boat_specs = boat.get('specs') or {}
            boat_specs, spec_changes = merge_specs(boat_specs, dp['specs'])
            if spec_changes:
                boat['specs'] = boat_specs
                boat_changes.extend(spec_changes)

        # Merge builder
        if dp.get('builder') and is_empty(boat.get('builder')):
            boat['builder'] = dp['builder']
            boat_changes.append(f"builder = {dp['builder']}")

        if boat_changes:
            boats[idx] = boat
            changes_log.append(f"D.{dn} {boat.get('name', '')}: {', '.join(boat_changes)}")
            print(f"  D.{dn}: {', '.join(boat_changes)}")
        else:
            print(f"  D.{dn}: no changes needed")

    # ── Merge design list data (cross-reference) ──
    print(f"\n{'─' * 40}")
    print("Cross-referencing design list...")

    dl_updates = 0
    for entry in muse.get('design_list_entries', []):
        dn = entry['designNumber']
        if dn not in boats_idx:
            continue

        idx = boats_idx[dn]
        boat = boats[idx]
        entry_changes = []

        # Fill year if missing
        if entry.get('year') and not boat.get('year'):
            boat['year'] = entry['year']
            entry_changes.append(f"year = {entry['year']}")

        # Fill name if missing
        if entry.get('name') and is_empty(boat.get('name')):
            boat['name'] = entry['name']
            entry_changes.append(f"name = {entry['name']}")

        # Fill shortDescription if missing
        if entry.get('type') and is_empty(boat.get('shortDescription')):
            boat['shortDescription'] = entry['type']
            entry_changes.append(f"shortDescription = {entry['type']}")

        if entry_changes:
            boats[idx] = boat
            dl_updates += 1
            changes_log.append(f"D.{dn} (design list): {', '.join(entry_changes)}")

    print(f"  Updated {dl_updates} existing designs from design list")

    # ── Merge size data (LOA from size list) ──
    print(f"\n{'─' * 40}")
    print("Merging LOA from size list...")

    size_fills = 0
    for dn, size_ft in muse.get('size_data', {}).items():
        if dn not in boats_idx:
            continue

        idx = boats_idx[dn]
        boat = boats[idx]
        specs = boat.get('specs') or {}
        loa = specs.get('loa') or {}

        if not loa.get('ft') and not loa.get('m'):
            if not specs:
                boat['specs'] = {}
            if 'loa' not in boat['specs']:
                boat['specs']['loa'] = {}
            boat['specs']['loa']['ft'] = size_ft
            boats[idx] = boat
            size_fills += 1
            changes_log.append(f"D.{dn}: loa.ft = {size_ft} (from size list)")

    print(f"  Filled LOA for {size_fills} designs")

    # ── Add new designs from design list ──
    print(f"\n{'─' * 40}")
    print("Adding new designs from design list...")

    new_count = 0
    for entry in muse.get('design_list_new', []):
        dn = entry['designNumber']
        size_ft = muse.get('size_data', {}).get(dn)
        new_boat = create_new_design(entry, size_ft)
        boats.append(new_boat)
        new_count += 1
        changes_log.append(f"D.{dn} {entry.get('name', '?')}: NEW DESIGN ADDED")
        print(f"  Added D.{dn} {entry.get('name', '?')} ({entry.get('year', '?')}) - {entry.get('type', '?')}")

    print(f"  Added {new_count} new designs")

    # ── Sort boats by designNumber ──
    def sort_key(b):
        dn = str(b.get('designNumber', ''))
        # Handle variant numbers like "609M"
        m = re.match(r'^(\d+)', dn)
        if m:
            return (int(m.group(1)), dn)
        return (999999, dn)

    boats.sort(key=sort_key)

    # ── Write output ──
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(boats, f, indent=2, ensure_ascii=False)

    # ── Summary ──
    print(f"\n{'═' * 60}")
    print("MERGE SUMMARY")
    print(f"{'═' * 60}")
    print(f"  Total changes: {len(changes_log)}")
    print(f"  Designs with description added: {sum(1 for c in changes_log if 'description' in c)}")
    print(f"  Designs with specs added: {sum(1 for c in changes_log if any(s in c for s in ['loa', 'beam', 'draft', 'displacement', 'ballast', 'dwl', 'lwl']))}")
    print(f"  Designs with builder added: {sum(1 for c in changes_log if 'builder' in c)}")
    print(f"  New designs added: {new_count}")
    print(f"  LOA filled from size list: {size_fills}")
    print(f"  Final boats.json count: {len(boats)}")
    print(f"\n  Changes written to {OUTPUT_JSON}")
    print(f"  Backup at {BACKUP_JSON}")

    # Write change log
    with open('muse_merge_log.txt', 'w') as f:
        f.write("MUSE Data Merge — Change Log\n")
        f.write("=" * 40 + "\n\n")
        for change in changes_log:
            f.write(change + "\n")
    print(f"  Change log at muse_merge_log.txt")


if __name__ == "__main__":
    main()
