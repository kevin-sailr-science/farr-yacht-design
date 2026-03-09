#!/usr/bin/env python3
"""
repoint_to_wp_cdn.py
Replaces all local images/{slug}.ext background-image references in HTML files
with full WP CDN URLs from wire_images_report.json.

Usage:
  python3 repoint_to_wp_cdn.py

Expects wire_images_report.json in the same directory.
Rewrites all .html files in the current directory and yacht/ subdirectory in-place.
Prints a summary of changes and any slugs with no manifest match.
"""

import json
import re
import os
import sys

# ── Config ────────────────────────────────────────────────────────────────────

MANIFEST_FILE = 'wire_images_report.json'
CDN_BASE = 'https://farrdesign.com/wp-content/uploads/'

# Directories to scan for HTML files
SCAN_DIRS = ['.', 'yacht']

# Pattern: background-image:url('images/anything.ext')
# Also catches background-image: url('images/...') with a space
LOCAL_IMG_RE = re.compile(r"(background-image\s*:\s*url\(\s*['\"])(images/)([^'\"]+)(['\"])")

# ── Load manifest ─────────────────────────────────────────────────────────────

if not os.path.exists(MANIFEST_FILE):
    print(f"ERROR: {MANIFEST_FILE} not found in current directory.")
    sys.exit(1)

with open(MANIFEST_FILE, encoding='utf-8') as f:
    manifest = json.load(f)

# Build slug -> full CDN URL
cdn_map = {}
for slug, data in manifest.items():
    if data and data.get('image'):
        # manifest paths are like "images/2025/10/file.jpg" — strip the "images/" prefix
        path = data['image'].replace('images/', '', 1)
        cdn_map[slug] = CDN_BASE + path

print(f"Loaded {len(cdn_map)} CDN mappings from manifest ({len(manifest) - len(cdn_map)} null/missing).")

# ── Collect HTML files ────────────────────────────────────────────────────────

html_files = []
for d in SCAN_DIRS:
    if os.path.isdir(d):
        for fname in os.listdir(d):
            if fname.endswith('.html'):
                html_files.append(os.path.join(d, fname))

html_files.sort()
print(f"Found {len(html_files)} HTML files to process.\n")

# ── Process files ─────────────────────────────────────────────────────────────

total_replaced = 0
total_missed = 0
no_match = {}  # slug -> list of files where it appeared

for filepath in html_files:
    raw = open(filepath, 'rb').read()

    # Encoding safety
    if raw[:3] == b'\xef\xbb\xbf':
        print(f"  WARNING: BOM detected in {filepath} — stripping")
        raw = raw[3:]

    html = raw.decode('utf-8')
    file_replaced = 0
    file_missed = 0

    def replacer(m):
        global file_replaced, file_missed
        prefix = m.group(1)   # background-image:url('
        images_dir = m.group(2)  # images/
        path_and_ext = m.group(3)  # e.g. volvo-ocean-65.jpg
        quote = m.group(4)    # '

        # Extract slug: strip file extension
        slug = re.sub(r'\.[^.]+$', '', path_and_ext)

        if slug in cdn_map:
            file_replaced += 1
            return prefix + cdn_map[slug] + quote
        else:
            file_missed += 1
            no_match.setdefault(slug, []).append(filepath)
            return m.group(0)  # leave unchanged

    new_html = LOCAL_IMG_RE.sub(replacer, html)

    if file_replaced > 0 or file_missed > 0:
        if file_replaced > 0:
            # Write back only if changed
            out = new_html.encode('utf-8')
            if sum(1 for b in out if b > 127) > 0:
                print(f"  ERROR: non-ASCII bytes in output for {filepath} — skipping write")
            else:
                open(filepath, 'wb').write(out)

        status = f"  {filepath}: {file_replaced} replaced"
        if file_missed:
            status += f", {file_missed} unmatched"
        print(status)
        total_replaced += file_replaced
        total_missed += file_missed

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"Total replaced : {total_replaced}")
print(f"Total unmatched: {total_missed}")

if no_match:
    print(f"\nUnmatched slugs (no entry in manifest):")
    for slug, files in sorted(no_match.items()):
        print(f"  {slug}")
        for f in files:
            print(f"    in {f}")
