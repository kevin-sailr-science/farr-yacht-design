#!/usr/bin/env python3
"""
extract_muse.py — Sprint 7: MUSE Data Extraction

Parses 10 MUSE design pages from Scripts/ and the design list from Temp/
to extract specs, descriptions, and metadata for merging into boats.json.

Output: muse_extracted.json (for review before merge)
"""

import json
import re
import os
from html.parser import HTMLParser

SCRIPTS_DIR = "Scripts"
TEMP_DIR = "Temp"
BOATS_JSON = "_data/boats.json"
OUTPUT_FILE = "muse_extracted.json"

# Known MUSE design pages with their design numbers
MUSE_PAGES = {
    "768-copy.html": {"designNumber": "778", "expectedName": "Southern Wind 105"},
    "781-copy-copy.html": {"designNumber": "813", "expectedName": "14m Tender"},
    "781-copy.html": {"designNumber": "828", "expectedName": "Expedition Rowing/Sailing Craft"},
    "784-copy-2.html": {"designNumber": "826", "expectedName": "IMOCA Open 60"},
    "784-copy.html": {"designNumber": "842", "expectedName": "55ft One Design"},
    "788.html": {"designNumber": "788", "expectedName": "Baltic 142 Custom"},
    "809.html": {"designNumber": "809", "expectedName": "50M Superyacht"},
    "819.html": {"designNumber": "819", "expectedName": "Najad 395 AC/CC"},
    "fyd--design-841-fast-40-.html": {"designNumber": "841", "expectedName": "Fast 40+"},
    "fyd--farr-43-(design-844).html": {"designNumber": "844", "expectedName": "Farr 43"},
}


def strip_html(text):
    """Remove HTML tags and clean whitespace."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('\u201c', '"').replace('\u201d', '"')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_title(html):
    """Extract boat name and design number from <title> tag."""
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if m:
        title = strip_html(m.group(1))
        # Pattern: "FYD | Boat Name (Design NNN)"
        tm = re.search(r'FYD\s*\|\s*(.*?)(?:\s*\(Design\s*(\d+)\))?$', title)
        if tm:
            return tm.group(1).strip(), tm.group(2)
    return None, None


def parse_specs(html):
    """
    Extract spec labels and values from paired div blocks.
    MUSE pages use two sibling divs: one with labels (<p>LOA:</p>),
    one with values (<p>43.3 m / 142.06 ft</p>).
    """
    specs = {}

    # Strategy: find any <p> containing a known spec label ending with ":"
    # Then find the sibling div with corresponding values
    spec_keywords = ['LOA', 'LWL', 'DWL', 'Beam', 'Draft', 'Displacement', 'Ballast',
                     'Cant Angle', 'Light CE Displacement', 'Target IRC']

    # Find the label div by looking for <p>LOA:</p> as the anchor
    loa_idx = html.find('<p>LOA:')
    if loa_idx < 0:
        # Try alternate spec labels
        for kw in ['Beam:', 'Draft:', 'Light CE']:
            loa_idx = html.find(f'<p>{kw}')
            if loa_idx >= 0:
                break

    if loa_idx < 0:
        return specs

    # Walk backward to find the containing div
    div_start = html.rfind('<div', 0, loa_idx)
    # Walk forward to find the closing </div>
    div_end = html.find('</div>', loa_idx)

    if div_start < 0 or div_end < 0:
        return specs

    label_block = html[div_start:div_end + 6]
    labels = re.findall(r'<p>\s*([^<]+?)\s*</p>', label_block)
    labels = [l.rstrip(':').strip() for l in labels if l.strip()]

    # The value div follows immediately after the label div
    remaining = html[div_end + 6:]
    value_match = re.search(r'<div[^>]*>.*?((?:<p>[^<]*</p>\s*)+)\s*</div>', remaining, re.DOTALL)
    if value_match:
        values = re.findall(r'<p>\s*([^<]+?)\s*</p>', value_match.group(0))
        values = [v.strip() for v in values if v.strip()]

        for label, value in zip(labels, values):
            if not value or value == '&nbsp;':
                continue

            label_key = label.lower().strip()

            parsed = parse_measurement(value)
            if parsed:
                specs[label_key] = parsed
            else:
                specs[label_key] = {"raw": value}

    return specs


def parse_measurement(value_str):
    """Parse a measurement string like '43.3 m / 142.06 ft' into metric and imperial."""
    value_str = value_str.strip()

    # Pattern: "43.3 m / 142.06 ft"
    m = re.match(r'([\d,.]+)\s*(m|tons|kg)\s*/\s*([\d,.]+)\s*(ft|lbs)', value_str)
    if m:
        metric_val = float(m.group(1).replace(',', ''))
        metric_unit = m.group(2)
        imperial_val = float(m.group(3).replace(',', ''))
        imperial_unit = m.group(4)
        return {
            "m": metric_val if metric_unit == 'm' else None,
            "ft": imperial_val if imperial_unit == 'ft' else None,
            "kg": metric_val if metric_unit == 'kg' else None,
            "lbs": imperial_val if imperial_unit == 'lbs' else None,
            "tons": metric_val if metric_unit == 'tons' else None,
            "raw": value_str
        }

    # Pattern: "134 tons / 268,000 lbs"
    m = re.match(r'([\d,.]+)\s*tons?\s*/\s*([\d,.]+)\s*lbs', value_str)
    if m:
        return {
            "tons": float(m.group(1).replace(',', '')),
            "lbs": float(m.group(2).replace(',', '')),
            "raw": value_str
        }

    # Pattern with degrees: "38 Degrees"
    m = re.match(r'([\d,.]+)\s*[Dd]egrees?', value_str)
    if m:
        return {"degrees": float(m.group(1).replace(',', '')), "raw": value_str}

    return None


def parse_description(html):
    """Extract description paragraphs from the main content area."""
    descriptions = []

    # Skip words that indicate navigation/UI elements, not descriptions
    skip_texts = {
        'MORE INFORMATION', 'SUPERYACHTS', 'RACE YACHTS', 'PRODUCTION YACHTS',
        'CRUISING YACHTS', "AMERICA'S CUP", '< Back to all designs',
        'CONCEPTS', 'POWER YACHTS', 'ONE DESIGNS', 'FARR YACHT DESIGN',
    }

    # Strategy 1: Find content divs with shared_content class
    content_blocks = re.finditer(
        r'<div[^>]*class="[^"]*shared_content[^"]*"[^>]*><!-- content -->\s*((?:<p>.*?</p>\s*)+)\s*</div>',
        html, re.DOTALL
    )

    for block in content_blocks:
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', block.group(1), re.DOTALL)
        for p in paragraphs:
            text = strip_html(p).strip()
            if _is_description_text(text, skip_texts):
                descriptions.append(text)

    # Strategy 2: If no descriptions found from shared_content, search all <p> tags
    # for substantial text that looks like yacht descriptions
    if not descriptions:
        all_paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        for p in all_paragraphs:
            text = strip_html(p).strip()
            if _is_description_text(text, skip_texts) and len(text) > 60:
                # Extra filter: must not be form/UI text
                if not any(kw in text.lower() for kw in ['submit', 'email us at', 'sign up for',
                                                          'error submitting', 'inquiry was received',
                                                          'sketchfab', 'on sketchfab']):
                    descriptions.append(text)

    return '\n\n'.join(descriptions) if descriptions else None


def _is_description_text(text, skip_texts):
    """Check if text looks like a description paragraph."""
    return (text and
            text != '&nbsp;' and
            len(text) > 30 and
            not text.endswith(':') and
            not text.startswith('<') and
            text.upper() not in skip_texts and
            not re.match(r'^[\d.]+\s*(m|ft|kg|lbs|tons)', text) and  # Skip spec values
            not re.match(r'^Design \d+', text))


def parse_images(html, filename):
    """Extract image references from the page."""
    images = []

    # Find data-orig-src attributes (MUSE lazy-loads images)
    for m in re.finditer(r'data-orig-src="([^"]+)"', html):
        src = m.group(1)
        # Filter out common UI images
        if any(skip in src.lower() for skip in ['logo', 'facebook', 'twitter', 'youtube',
                                                   'google', 'instagram', 'blank.gif', 'icon',
                                                   'arrow', 'menu', 'nav']):
            continue
        # Clean CRC suffix
        src = re.sub(r'\?crc=\d+$', '', src)
        if src not in images:
            images.append(src)

    # Also check for lightgallery image references
    for m in re.finditer(r'data-src="([^"]+)"', html):
        src = m.group(1)
        src = re.sub(r'\?crc=\d+$', '', src)
        if src not in images and 'blank' not in src:
            images.append(src)

    return images


def parse_builder(html):
    """Extract builder info from 'Visit the builder's website' links and description text."""
    builder_name = None
    builder_url = None

    # Look for "Visit the builder's website" link (may use curly or straight apostrophe)
    m = re.search(r'Visit the builder.{1,3}s website.*?href="(https?://[^"]+)"', html, re.DOTALL)
    if not m:
        # Also try: the link is nearby in another element
        m = re.search(r'href="(https?://[^"]+)"[^>]*>.*?Visit the builder', html, re.DOTALL)

    # Check for builder-related URLs near "Visit the builder"
    if not m:
        # Find the builder link by looking for known builder domains
        for domain_match in re.finditer(r'href="(https?://(?:www\.)?(balticyachts|southernwind|najad|infiniti|premier)[^"]*)"', html, re.IGNORECASE):
            builder_url = domain_match.group(1)
            break

    if m:
        builder_url = m.group(1)

    # Map known URLs to builder names
    if builder_url:
        builder_map = {
            'balticyachts': 'Baltic Yachts',
            'southernwind': 'Southern Wind Shipyard',
            'najad': 'Najad Yachts',
            'vanmunster': 'Van Munster Boats',
        }
        for key, name in builder_map.items():
            if key in builder_url.lower():
                builder_name = name
                break

    # Also check description text for builder mentions
    if not builder_name:
        text = strip_html(html)
        builder_patterns = [
            (r'built by\s+([A-Z][A-Za-z\s]+?)(?:\.|,|\s+and)', lambda m: m.group(1).strip()),
            (r'Van Munster\s+(?:boats?|boatbuilder)?', lambda m: 'Van Munster Boats'),
            (r'Tenderworks', lambda m: 'Tenderworks'),
        ]
        for pattern, extractor in builder_patterns:
            bm = re.search(pattern, text, re.IGNORECASE)
            if bm:
                builder_name = extractor(bm)
                break

    return builder_name, builder_url


def parse_year_from_description(description):
    """Try to extract year from description context."""
    if not description:
        return None
    # Look for "commissioned in YYYY" or "launched in YYYY" etc
    m = re.search(r'(?:commissioned|launched|designed|built|completed)\s+in\s+(\d{4})', description, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_design_page(filepath, page_info):
    """Parse a single MUSE design page and extract all available data."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    title_name, title_design_num = parse_title(html)
    specs = parse_specs(html)
    description = parse_description(html)
    images = parse_images(html, os.path.basename(filepath))
    builder_name, builder_url = parse_builder(html)

    result = {
        "source": f"Scripts/{os.path.basename(filepath)}",
        "designNumber": page_info["designNumber"],
        "boatName": title_name or page_info["expectedName"],
        "specs": specs,
        "description": description,
        "images": images,
        "builder": builder_name,
        "builderUrl": builder_url,
    }

    # Extract year from description if available
    year = parse_year_from_description(description)
    if year:
        result["year"] = year

    return result


def parse_design_list(filepath):
    """Parse design_list.html to extract design number, year, type, and name.
    Structure: <tr><td><p3>NNN - YYYY</p3></td><td><p3>type</p3></td><td><p3>name</p3></td></tr>
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    entries = []

    # Find all table rows with 3 cells
    rows = re.finditer(r'<tr>\s*(.*?)\s*</tr>', content, re.DOTALL)

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row.group(1), re.DOTALL)
        if len(cells) < 3:
            continue

        # First cell: design number and year (may be wrapped in <a> and <p3>)
        cell1_text = strip_html(cells[0]).strip()
        m = re.match(r'(\d+)\s*-\s*((?:19|20)\d{2})', cell1_text)
        if not m:
            continue

        cell2_text = strip_html(cells[1]).strip()
        cell3_text = strip_html(cells[2]).strip()

        entries.append({
            "designNumber": m.group(1),
            "year": int(m.group(2)),
            "type": cell2_text if cell2_text else None,
            "name": cell3_text if cell3_text else None,
        })

    return entries


def parse_design_list_size(filepath):
    """Parse design_list-size.html to extract size (ft) for each design.
    Structure: <tr><td>size_ft</td><td>NNN - YYYY</td><td>type</td><td>name</td></tr>
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    size_map = {}

    rows = re.finditer(r'<tr>\s*(.*?)\s*</tr>', content, re.DOTALL)

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row.group(1), re.DOTALL)
        if len(cells) < 4:
            continue

        size_text = strip_html(cells[0]).strip()
        dn_text = strip_html(cells[1]).strip()

        # Size should be a number
        size_m = re.match(r'^([\d.]+)$', size_text)
        dn_m = re.match(r'(\d+)\s*-\s*((?:19|20)\d{2})', dn_text)

        if size_m and dn_m:
            size_ft = float(size_m.group(1))
            design_num = dn_m.group(1)
            size_map[design_num] = size_ft

    return size_map


def main():
    print("=" * 60)
    print("MUSE Data Extraction — Sprint 7")
    print("=" * 60)

    # Load current boats.json for comparison
    with open(BOATS_JSON) as f:
        boats = json.load(f)
    existing = {str(b["designNumber"]): b for b in boats}
    print(f"\nCurrent boats.json: {len(boats)} designs")

    results = {
        "design_pages": [],
        "design_list_entries": [],
        "design_list_new": [],  # Entries not in boats.json
        "size_data": {},
        "summary": {},
    }

    # ── Parse 10 MUSE design pages ──
    print(f"\n{'─' * 40}")
    print("Parsing MUSE design pages...")

    for filename, page_info in MUSE_PAGES.items():
        filepath = os.path.join(SCRIPTS_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  WARNING: {filepath} not found")
            continue

        data = parse_design_page(filepath, page_info)
        results["design_pages"].append(data)

        dn = data["designNumber"]
        in_json = "EXISTS" if dn in existing else "NEW"
        spec_count = len(data["specs"])
        desc_len = len(data["description"]) if data["description"] else 0
        img_count = len(data["images"])

        print(f"  D.{dn} {data['boatName']:30s} [{in_json}] specs={spec_count} desc={desc_len}ch imgs={img_count}")

    # ── Parse design list ──
    print(f"\n{'─' * 40}")
    print("Parsing design_list.html...")

    dl_path = os.path.join(TEMP_DIR, "design_list.html")
    if os.path.exists(dl_path):
        entries = parse_design_list(dl_path)
        results["design_list_entries"] = entries
        print(f"  Extracted {len(entries)} entries")

        # Find entries not in boats.json
        for entry in entries:
            dn = entry["designNumber"]
            if dn not in existing:
                results["design_list_new"].append(entry)

        print(f"  New (not in boats.json): {len(results['design_list_new'])}")
        for entry in results["design_list_new"]:
            print(f"    D.{entry['designNumber']:>4s} ({entry['year']}) {entry.get('type', '?'):30s} {entry.get('name', '?')}")

    # ── Parse design list by size ──
    print(f"\n{'─' * 40}")
    print("Parsing design_list-size.html...")

    dls_path = os.path.join(TEMP_DIR, "design_list-size.html")
    if os.path.exists(dls_path):
        size_map = parse_design_list_size(dls_path)
        results["size_data"] = size_map
        print(f"  Extracted sizes for {len(size_map)} designs")

        # How many fill gaps in boats.json?
        fills = 0
        for dn, size_ft in size_map.items():
            if dn in existing:
                b = existing[dn]
                specs = b.get("specs") or {}
                loa = specs.get("loa") or {}
                if not loa.get("ft") and not loa.get("m"):
                    fills += 1
        print(f"  Would fill {fills} missing LOA values in boats.json")

    # ── Summary ──
    print(f"\n{'═' * 60}")
    print("SUMMARY")
    print(f"{'═' * 60}")

    new_designs = [d for d in results["design_pages"] if d["designNumber"] not in existing]
    update_designs = [d for d in results["design_pages"] if d["designNumber"] in existing]

    total_specs = sum(len(d["specs"]) for d in results["design_pages"])
    total_with_desc = sum(1 for d in results["design_pages"] if d["description"])
    total_with_builder = sum(1 for d in results["design_pages"] if d["builder"])
    total_images = sum(len(d["images"]) for d in results["design_pages"])

    results["summary"] = {
        "design_pages_parsed": len(results["design_pages"]),
        "new_designs_from_pages": len(new_designs),
        "existing_designs_updated": len(update_designs),
        "total_spec_values": total_specs,
        "pages_with_description": total_with_desc,
        "pages_with_builder": total_with_builder,
        "total_image_refs": total_images,
        "design_list_total": len(results["design_list_entries"]),
        "design_list_new": len(results["design_list_new"]),
        "sizes_extracted": len(results.get("size_data", {})),
    }

    print(f"  Design pages parsed: {results['summary']['design_pages_parsed']}")
    print(f"  New designs (not in boats.json): {results['summary']['new_designs_from_pages']}")
    print(f"  Total spec values extracted: {results['summary']['total_spec_values']}")
    print(f"  Pages with descriptions: {results['summary']['pages_with_description']}")
    print(f"  Pages with builder info: {results['summary']['pages_with_builder']}")
    print(f"  Total image references: {results['summary']['total_image_refs']}")
    print(f"  Design list entries: {results['summary']['design_list_total']}")
    print(f"  New from design list: {results['summary']['design_list_new']}")
    print(f"  Size data extracted: {results['summary']['sizes_extracted']}")

    # Write output
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nOutput written to {OUTPUT_FILE}")
    print("Review before merging into boats.json!")


if __name__ == "__main__":
    main()
