#!/usr/bin/env python3
"""
Bulk-rename all yacht images to canonical naming convention.

Convention:
  Yacht images:    {designNumber}-hero.{ext}  (designated primary)
                   {designNumber}-{descriptor}-v{N}.{ext}  (gallery/extras)
  Campaign images: {context}-{descriptor}.{ext}  (non-yacht images)

Usage:
  python rename_images.py --dry-run          # Preview changes
  python rename_images.py --execute          # Execute renames
  python rename_images.py --rollback         # Undo using manifest

Sprint IMG-42 — Farr Yacht Design website project.
"""
import json, os, re, sys, shutil, argparse
from collections import defaultdict
from pathlib import Path

WWW = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(WWW, "images")
BOATS_JSON = os.path.join(WWW, "_data", "boats.json")
MANIFEST_FILE = os.path.join(WWW, "rename_manifest.json")
BOATS_BACKUP = os.path.join(WWW, "_data", "boats.json.pre-rename")

# ─── Helpers ───

def slugify(s):
    """Convert a string to a clean descriptor slug."""
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s or "photo"

def get_descriptor_from_filename(old_name, design_num):
    """Extract a meaningful descriptor from an old filename."""
    base = os.path.splitext(old_name)[0]

    # Strip design number prefix
    base = re.sub(rf'^0*{re.escape(str(design_num))}[_-]?', '', base, flags=re.I)

    # Strip UUID prefix
    base = re.sub(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-?', '', base, flags=re.I)

    # Strip SW10802_ prefix pattern
    base = re.sub(r'^SW\d+_', '', base, flags=re.I)

    # Strip _resize suffix
    base = re.sub(r'_resize(\s*\(\d+\))?$', '', base, flags=re.I)

    # Strip leading/trailing separators
    base = base.strip('_- ')

    if not base:
        return "photo"

    return slugify(base)

def is_webp_pair(filename, all_files_lower):
    """Check if this file has a corresponding WebP pair."""
    base = os.path.splitext(filename)[0].lower()
    return f"{base}.webp" in all_files_lower

# ─── Main logic ───

def build_rename_plan(boats, all_files):
    """Build the full rename mapping."""
    all_files_lower = {f.lower() for f in all_files}

    # Build design number → boat lookup
    dn_to_boat = {}
    for b in boats:
        dn = str(b.get('designNumber', ''))
        if dn:
            dn_to_boat[dn] = b

    # Build reverse lookup: image filename → design number(s)
    img_to_designs = defaultdict(set)
    for b in boats:
        dn = str(b.get('designNumber', ''))
        imgs = b.get('images', {}) or {}
        if imgs.get('hero'):
            img_to_designs[imgs['hero']].add(dn)
        for g in (imgs.get('gallery') or []):
            img_to_designs[g].add(dn)

    renames = {}          # old_name → new_name
    design_counters = defaultdict(int)  # design_num → next version number
    hero_designations = {}  # design_num → hero filename (new)
    ambiguous = []         # files that couldn't be mapped
    skipped = []           # files intentionally skipped

    # Collect all image refs per design number (prefer visible boats)
    dn_images = defaultdict(lambda: {"hero": None, "gallery": []})
    for b in boats:
        dn = str(b.get('designNumber', ''))
        if not dn:
            continue
        is_hidden = b.get('hidden') == 1
        imgs = b.get('images', {}) or {}

        hero = imgs.get('hero', '')
        gallery = imgs.get('gallery') or []

        # Only set hero if not already set (prefer visible boat's hero)
        if hero and hero in all_files:
            if dn_images[dn]["hero"] is None or not is_hidden:
                dn_images[dn]["hero"] = hero
        # Accumulate all gallery images
        for g in gallery:
            if g in all_files and g not in dn_images[dn]["gallery"]:
                dn_images[dn]["gallery"].append(g)

    processed_files = set()  # track files already assigned

    # Phase 1: Process yacht-linked images (hero + gallery per design number)
    for dn, img_data in dn_images.items():
        # Hero image
        hero_file = img_data["hero"]
        if hero_file and hero_file not in processed_files:
            old_ext = os.path.splitext(hero_file)[1].lower()
            new_hero = f"{dn}-hero{old_ext}"
            if hero_file != new_hero:
                renames[hero_file] = new_hero
            hero_designations[dn] = new_hero
            processed_files.add(hero_file)

            # Also rename WebP pair if exists
            webp_name = os.path.splitext(hero_file)[0] + ".webp"
            if webp_name in all_files and old_ext != '.webp' and webp_name not in processed_files:
                new_webp = f"{dn}-hero.webp"
                if webp_name != new_webp:
                    renames[webp_name] = new_webp
                processed_files.add(webp_name)

        # Gallery images (skip hero if it appears in gallery too)
        for g_file in img_data["gallery"]:
            if g_file in processed_files:
                continue
            old_ext = os.path.splitext(g_file)[1].lower()
            descriptor = get_descriptor_from_filename(g_file, dn)
            design_counters[dn] += 1
            v = design_counters[dn]
            new_name = f"{dn}-{descriptor}-v{v}{old_ext}"
            if g_file != new_name:
                renames[g_file] = new_name
            processed_files.add(g_file)

            # WebP pair
            webp_name = os.path.splitext(g_file)[0] + ".webp"
            if webp_name in all_files and old_ext != '.webp' and webp_name not in processed_files:
                new_webp = f"{dn}-{descriptor}-v{v}.webp"
                if webp_name != new_webp:
                    renames[webp_name] = new_webp
                processed_files.add(webp_name)

    # Phase 2: Process unlinked images that match design number patterns
    for f in all_files:
        if f in renames or f in processed_files:
            continue  # already handled
        base, ext = os.path.splitext(f)
        ext_lower = ext.lower()
        if ext_lower not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'):
            skipped.append(f)
            continue

        # Try to match to a design number
        m = re.match(r'^(\d+)', base)
        if m:
            num = m.group(1)
            # Try both with and without leading zeros
            dn = None
            if num in dn_to_boat:
                dn = num
            elif num.lstrip('0') in dn_to_boat:
                dn = num.lstrip('0')

            if dn:
                # Check if this is already in the correct format
                if re.match(rf'^{re.escape(dn)}-hero\.(jpg|jpeg|png|webp)$', f, re.I):
                    continue
                if re.match(rf'^{re.escape(dn)}-[\w-]+-v\d+\.(jpg|jpeg|png|webp)$', f, re.I):
                    continue

                descriptor = get_descriptor_from_filename(f, dn)
                # Is this the hero? (plain design number filename)
                if re.match(rf'^0*{re.escape(dn)}\.(jpg|jpeg|png|gif)$', f, re.I):
                    # This is a plain number file — it's the hero if no hero already set
                    if dn not in hero_designations:
                        new_name = f"{dn}-hero{ext_lower}"
                        if f != new_name:
                            renames[f] = new_name
                        hero_designations[dn] = new_name
                    else:
                        # Already have a hero, this becomes a gallery image
                        design_counters[dn] += 1
                        v = design_counters[dn]
                        new_name = f"{dn}-{descriptor}-v{v}{ext_lower}"
                        if f != new_name:
                            renames[f] = new_name
                elif re.match(rf'^0*{re.escape(dn)}\.webp$', f, re.I):
                    # WebP version of plain number — hero webp if slot available
                    target_webp = f"{dn}-hero.webp"
                    if target_webp.lower() not in {v.lower() for v in renames.values()}:
                        new_name = target_webp
                    else:
                        design_counters[dn] += 1
                        v = design_counters[dn]
                        new_name = f"{dn}-{descriptor}-v{v}.webp"
                    if f != new_name:
                        renames[f] = new_name
                else:
                    # Variant / gallery image
                    # For WebP files, check if JPG counterpart was already renamed and use matching name
                    if ext_lower == '.webp':
                        jpg_counterpart = os.path.splitext(f)[0] + ".jpg"
                        if jpg_counterpart in renames:
                            new_name = os.path.splitext(renames[jpg_counterpart])[0] + ".webp"
                            if f != new_name:
                                renames[f] = new_name
                            continue
                    design_counters[dn] += 1
                    v = design_counters[dn]
                    new_name = f"{dn}-{descriptor}-v{v}{ext_lower}"
                    if f != new_name:
                        renames[f] = new_name
                continue

        # Check if referenced in boats.json by any design
        if f in img_to_designs:
            dns = list(img_to_designs[f])
            dn = dns[0]  # use first design if multiple
            descriptor = get_descriptor_from_filename(f, dn)
            design_counters[dn] += 1
            v = design_counters[dn]
            new_name = f"{dn}-{descriptor}-v{v}{ext_lower}"
            if f != new_name:
                renames[f] = new_name
            continue

        # Campaign / non-yacht images — keep or slugify
        if ext_lower in ('.svg',):
            skipped.append(f)
            continue

        # UUID-prefixed → strip UUID
        if re.match(r'^[0-9a-f]{8}-', f, re.I):
            clean = re.sub(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-?', '', f)
            if clean and clean != f:
                new_name = slugify(os.path.splitext(clean)[0]) + ext_lower
                if new_name != f:
                    renames[f] = new_name
                continue

        # Already clean slug? Skip
        if re.match(r'^[a-z0-9][a-z0-9-]+\.(jpg|jpeg|png|webp|gif)$', f):
            continue

        # Otherwise try to clean it up
        clean_name = slugify(base) + ext_lower
        if clean_name != f and clean_name != ext_lower:
            renames[f] = clean_name
        else:
            ambiguous.append(f)

    # Detect collisions
    new_names = defaultdict(list)
    for old, new in renames.items():
        new_names[new.lower()].append(old)

    collisions = {k: v for k, v in new_names.items() if len(v) > 1}

    # Resolve collisions by adding version suffixes
    for new_lower, old_files in collisions.items():
        for i, old in enumerate(old_files):
            base, ext = os.path.splitext(renames[old])
            # Add collision suffix
            renames[old] = f"{base}-dup{i+1}{ext}"

    return renames, hero_designations, ambiguous, skipped


def update_boats_json(boats, renames):
    """Update all image references in boats data."""
    changes = 0
    for b in boats:
        imgs = b.get('images', {}) or {}

        # Update hero
        if imgs.get('hero') and imgs['hero'] in renames:
            imgs['hero'] = renames[imgs['hero']]
            changes += 1

        # Update gallery
        gallery = imgs.get('gallery') or []
        new_gallery = []
        for g in gallery:
            if g in renames:
                new_gallery.append(renames[g])
                changes += 1
            else:
                new_gallery.append(g)
        if gallery:
            imgs['gallery'] = new_gallery

        # Update card
        if imgs.get('card') and imgs['card'] in renames:
            imgs['card'] = renames[imgs['card']]
            changes += 1

    return changes


def update_html_files(www_dir, renames):
    """Update image references in all HTML files."""
    changes = 0
    html_files = []
    for f in os.listdir(www_dir):
        if f.endswith('.html'):
            html_files.append(os.path.join(www_dir, f))

    for html_path in html_files:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content = content
        for old, new in renames.items():
            # Replace in image URLs (both quoted and unquoted)
            new_content = new_content.replace(f"images/{old}", f"images/{new}")
            new_content = new_content.replace(f"images/{old.replace(' ', '%20')}", f"images/{new}")

        if new_content != content:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            changes += 1

    return changes


def execute_renames(renames):
    """Rename files on disk."""
    success = 0
    errors = []
    for old, new in renames.items():
        old_path = os.path.join(IMAGES_DIR, old)
        new_path = os.path.join(IMAGES_DIR, new)
        if os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
                success += 1
            except Exception as e:
                errors.append(f"{old} → {new}: {e}")
        else:
            errors.append(f"{old}: file not found")
    return success, errors


def rollback(manifest):
    """Reverse renames using manifest."""
    renames = manifest.get("renames", {})
    reverse = {v: k for k, v in renames.items()}
    success, errors = 0, []
    for new, old in reverse.items():
        new_path = os.path.join(IMAGES_DIR, new)
        old_path = os.path.join(IMAGES_DIR, old)
        if os.path.exists(new_path):
            try:
                os.rename(new_path, old_path)
                success += 1
            except Exception as e:
                errors.append(f"{new} → {old}: {e}")
    # Restore boats.json
    if os.path.exists(BOATS_BACKUP):
        shutil.copy2(BOATS_BACKUP, BOATS_JSON)
        print(f"Restored boats.json from backup")
    return success, errors


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="Bulk rename images to canonical convention")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true', help='Preview changes without executing')
    group.add_argument('--execute', action='store_true', help='Execute renames')
    group.add_argument('--rollback', action='store_true', help='Rollback using manifest')
    args = parser.parse_args()

    if args.rollback:
        if not os.path.exists(MANIFEST_FILE):
            print("ERROR: No rename_manifest.json found")
            sys.exit(1)
        with open(MANIFEST_FILE) as f:
            manifest = json.load(f)
        success, errors = rollback(manifest)
        print(f"Rollback: {success} files restored, {len(errors)} errors")
        for e in errors:
            print(f"  ERROR: {e}")
        return

    # Load data
    with open(BOATS_JSON, 'r', encoding='utf-8') as f:
        boats = json.load(f)

    all_files = [f for f in os.listdir(IMAGES_DIR)
                 if os.path.isfile(os.path.join(IMAGES_DIR, f)) and not f.startswith('.')]

    # Build plan
    renames, heroes, ambiguous, skipped = build_rename_plan(boats, all_files)

    # Report
    print(f"{'='*60}")
    print(f"IMAGE RENAME {'DRY RUN' if args.dry_run else 'EXECUTION'}")
    print(f"{'='*60}")
    print(f"Total image files: {len(all_files)}")
    print(f"Files to rename: {len(renames)}")
    print(f"Files already correct: {len(all_files) - len(renames) - len(skipped) - len(ambiguous)}")
    print(f"Heroes designated: {len(heroes)}")
    print(f"Skipped (SVG/non-image): {len(skipped)}")
    print(f"Ambiguous (unmapped): {len(ambiguous)}")

    if renames:
        print(f"\n--- Sample renames (first 30) ---")
        for i, (old, new) in enumerate(sorted(renames.items())[:30]):
            print(f"  {old}")
            print(f"    → {new}")
        if len(renames) > 30:
            print(f"  ... and {len(renames) - 30} more")

    if ambiguous:
        print(f"\n--- Ambiguous files ---")
        for f in sorted(ambiguous)[:20]:
            print(f"  {f}")

    if args.dry_run:
        # Save dry-run report
        report = {
            "total_files": len(all_files),
            "renames": renames,
            "heroes": heroes,
            "ambiguous": ambiguous,
            "skipped": skipped,
        }
        report_path = os.path.join(WWW, "rename_dryrun.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nDry-run report saved to: rename_dryrun.json")
        print("Review and run with --execute to apply.")
        return

    # Execute
    print(f"\nExecuting {len(renames)} renames...")

    # Backup boats.json
    shutil.copy2(BOATS_JSON, BOATS_BACKUP)
    print(f"Backed up boats.json → boats.json.pre-rename")

    # Rename files on disk
    success, errors = execute_renames(renames)
    print(f"Files renamed: {success}, errors: {len(errors)}")
    for e in errors[:10]:
        print(f"  ERROR: {e}")

    # Update boats.json
    json_changes = update_boats_json(boats, renames)
    with open(BOATS_JSON, 'w', encoding='utf-8') as f:
        json.dump(boats, f, indent=2, ensure_ascii=False)
    print(f"boats.json references updated: {json_changes}")

    # Update HTML files
    html_changes = update_html_files(WWW, renames)
    print(f"HTML files updated: {html_changes}")

    # Save manifest
    manifest = {
        "date": "2026-03-14",
        "sprint": "IMG-42",
        "renames": renames,
        "heroes": heroes,
        "files_renamed": success,
        "json_refs_updated": json_changes,
        "html_files_updated": html_changes,
    }
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Manifest saved: rename_manifest.json")
    print(f"\nDone. Run build_site.py to regenerate yacht pages.")


if __name__ == "__main__":
    main()
