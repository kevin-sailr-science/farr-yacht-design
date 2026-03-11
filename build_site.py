#!/usr/bin/env python3
"""
Farr Yacht Design — Static Site Generator (v2 — Sprint 2)
Reads boats.json (with tier data), generates yacht detail pages with
tier-specific plan delivery UX, portfolio page, design-plans hub, and
copies static assets to _site/.
"""

import json
import os
import re
import shutil
import math
import html as html_module

# Paths — build_site.py now lives inside www/ (the Git repo root)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WWW = SCRIPT_DIR  # build_site.py is in www/, which IS the deploy root
SITE = WWW
DATA = os.path.join(SCRIPT_DIR, "_data", "boats.json")

# ─── Load data ───

with open(DATA) as f:
    all_boats = json.load(f)

# Filter out hidden designs (display=N in Britt's spreadsheet)
boats = [b for b in all_boats if not b.get("hidden")]

print(f"Loaded {len(all_boats)} boats from boats.json ({len(boats)} visible, {len(all_boats)-len(boats)} hidden)")

# ─── Helper functions ───

def decade(year):
    if not year:
        return "Unknown"
    try:
        return f"{(int(year) // 10) * 10}s"
    except (ValueError, TypeError):
        return "Unknown"

def clean_html(s):
    if not s:
        return ""
    s = str(s).lstrip("'")
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace('&nbsp;', ' ').replace('&#39;', "'").replace('&amp;', '&')
    s = s.replace('&quot;', '"').replace('&rsquo;', '\u2019').replace('&ldquo;', '\u201c')
    s = s.replace('&rdquo;', '\u201d').replace('&mdash;', '\u2014').replace('&ndash;', '\u2013')
    s = html_module.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def spec_cell(spec_obj):
    """Format a spec value with both imperial and metric units."""
    if not spec_obj or not isinstance(spec_obj, dict):
        return None
    parts = []
    ft = spec_obj.get('ft')
    m = spec_obj.get('m')
    lbs = spec_obj.get('lbs')
    kg = spec_obj.get('kg')
    sqft = spec_obj.get('sqft')
    sqm = spec_obj.get('sqm')
    if ft is not None:
        parts.append(f"{ft} ft")
    if lbs is not None and ft is None:
        parts.append(f"{int(lbs)} lbs")
    if sqft is not None and ft is None:
        parts.append(f"{sqft} sq ft")
    if m is not None:
        parts.append(f"{m} m")
    if kg is not None:
        parts.append(f"{int(kg)} kg")
    if sqm is not None and m is None:
        parts.append(f"{sqm} sq m")
    return " / ".join(parts) if parts else None

def esc(s):
    """HTML escape."""
    if not s:
        return ""
    return html_module.escape(str(s))

# ─── Check for existing images ───

images_dir = os.path.join(WWW, "images")
existing_images = set()
if os.path.isdir(images_dir):
    for f in os.listdir(images_dir):
        existing_images.add(f.lower())

# ─── Tier-specific plan section HTML ───

def build_plan_section(boat):
    """Generate the plan section HTML based on design tier and plan status."""
    tier = boat.get("tier", 3)
    plan_status = boat.get("planStatus", "coming_soon")
    has_card = boat.get("hasCardPDF", False)
    drawing_count = boat.get("cardDrawingCount")
    drawings_available = boat.get("cardDrawingsAvailable")
    design_num = boat.get("designNumber", "")

    # ─── TIER 1 WITH CARD PDF: "Plans Available" + purchase flow ───
    if tier == 1 and has_card:
        drawing_info = ""
        if drawing_count:
            drawing_info = f'<p style="font-size:0.82rem;color:var(--text-muted);margin:0.5rem 0 0;">{drawing_count} original drawings in this plan set'
            if drawings_available and drawings_available != drawing_count:
                drawing_info += f' ({drawings_available} available)'
            drawing_info += '</p>'

        return f'''
          <div class="purchase-card">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
              <h3 style="margin:0;">Design Plans</h3>
              <span class="availability-badge availability-badge--available">Available</span>
            </div>
            <p style="font-size:0.88rem;color:var(--text-secondary);line-height:1.6;margin-bottom:0.75rem;">Original design drawings from the Farr archive are available for this design. Plan set includes sail plans, lines drawings, and specifications as PDF download.</p>
            {drawing_info}
            <div style="margin-top:1rem;">
              <a href="/design-plans.html?design={esc(design_num)}" class="btn-purchase" style="text-decoration:none;">Purchase Plan Set</a>
            </div>
          </div>'''

    # ─── TIER 1 WITHOUT CARD PDF: "Plans not yet digitized" ───
    elif tier == 1 and not has_card:
        return f'''
          <div class="purchase-card purchase-card--waitlist">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
              <h3 style="margin:0;">Design Plans</h3>
              <span class="availability-badge availability-badge--coming">Digitizing</span>
            </div>
            <p class="purchase-waitlist-note">Plans for this design have not yet been digitized. Join the waitlist and we&rsquo;ll notify you as soon as plans are available for download.</p>
            <button class="btn-waitlist" onclick="window.location.href='/design-plans.html?design={esc(design_num)}'">Join Waitlist</button>
          </div>'''

    # ─── TIER 2: "Request from the Shed" ───
    elif tier == 2:
        drawing_info = ""
        if drawing_count:
            drawing_info = f'<p style="font-size:0.82rem;color:var(--text-muted);margin:0.5rem 0 0;">{drawing_count} drawings in physical archive</p>'

        return f'''
          <div class="purchase-card" style="background:linear-gradient(135deg, var(--panel) 0%, rgba(245, 158, 11, 0.04) 100%);border-color:rgba(245, 158, 11, 0.25);">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
              <h3 style="margin:0;">Design Plans</h3>
              <span class="availability-badge" style="color:#d97706;background:rgba(245,158,11,0.08);border-color:rgba(245,158,11,0.25);">Archive</span>
            </div>
            <p style="font-size:0.88rem;color:var(--text-secondary);line-height:1.6;margin-bottom:0.75rem;">This design&rsquo;s original drawings are in our physical archive in Annapolis. Request this plan set and we&rsquo;ll check availability and provide a quote.</p>
            {drawing_info}
            <div style="margin-top:1rem;">
              <a href="/design-plans.html?design={esc(design_num)}#waitlist-form" class="btn-waitlist" style="text-decoration:none;display:inline-block;background:transparent;color:#d97706;border-color:#d97706;">Request This Plan</a>
            </div>
          </div>'''

    # ─── TIER 3: "Coming Soon" ───
    else:
        return f'''
          <div class="purchase-card purchase-card--waitlist" style="opacity:0.7;">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
              <h3 style="margin:0;">Design Plans</h3>
              <span class="availability-badge availability-badge--unavailable">Coming Soon</span>
            </div>
            <p class="purchase-waitlist-note">Plan digitization for this design is in progress. Check back soon or <a href="/contact.html">contact us</a> for more information.</p>
          </div>'''


# ─── Generate yacht detail pages ───

def build_yacht_page(boat):
    """Generate a single yacht detail page HTML."""
    slug = boat.get("slug", "")
    display_name = boat.get("name") or boat.get("title", slug)
    display_number = boat.get("designNumber", "")
    year = boat.get("year")
    dec = decade(year)
    categories = boat.get("category") or []
    category = categories[0] if categories else ""
    design_rule = boat.get("designRule", "") or ""
    design_type = boat.get("designType", "") or ""
    classification = boat.get("classification", "") or ""
    specs = boat.get("specs") or {}

    # Meta line
    meta_parts = []
    if category:
        meta_parts.append(category)
    if design_rule:
        meta_parts.append(design_rule)
    if design_type and design_type != design_rule:
        meta_parts.append(design_type)
    meta_line = " | ".join(meta_parts)
    if not meta_line and year:
        meta_line = dec
    if meta_line and year:
        meta_line += f" | {year}"

    # Image — check images.main from boats.json first, then fall back to slug
    has_image = False
    image_url = f"/images/{slug}.jpg"
    img_main = (boat.get("images") or {}).get("main", "")
    if img_main and img_main.lower() in existing_images:
        has_image = True
        image_url = f"/images/{img_main}"
    else:
        for ext in [".jpg", ".jpeg", ".png", ".gif"]:
            if f"{slug}{ext}" in existing_images:
                has_image = True
                break

    img_tbc = ""
    if not has_image:
        img_tbc = '''<span class="img-tbc"><svg class="img-tbc-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/><circle cx="12" cy="14" r="3"/></svg><span class="img-tbc-label">Photo coming soon</span></span>'''

    # Description
    raw_desc = boat.get("description", "") or ""
    description = clean_html(raw_desc)
    short_desc = boat.get("shortDescription", "") or ""
    short_summary = clean_html(boat.get("shortSummary", "") or "")

    if len(description) > 20:
        display_desc = description
    elif short_summary and len(short_summary) > 20:
        display_desc = short_summary
    elif short_desc:
        display_desc = short_desc
    else:
        display_desc = f"{esc(display_name)} is a Farr Yacht Design"
        if year:
            display_desc += f" from {year}"
        if category:
            display_desc += f", built for {category.lower() if isinstance(category, str) else category}"
        display_desc += "."

    # Number display
    if display_number and str(display_number) != str(display_name):
        number_html = f"#{esc(display_number)}"
    else:
        number_html = f"#{esc(boat.get('title', slug))}"

    # Spec rows
    spec_rows = []
    if year:
        spec_rows.append(("Year", str(int(year)) if isinstance(year, float) else str(year)))
    if category:
        spec_rows.append(("Type", esc(category)))
    if design_rule:
        spec_rows.append(("Rule", esc(design_rule)))
    if design_type and design_type != design_rule:
        spec_rows.append(("Design Type", esc(design_type)))
    if classification:
        spec_rows.append(("Classification", esc(classification)))

    # Dimensional specs
    spec_fields = [
        ("loa", "LOA"), ("beam", "Beam"), ("lwl", "LWL"),
        ("draft", "Draft"), ("draftUp", "Draft (up)"),
        ("draftDown", "Draft (down)"),
        ("displacement", "Displacement"), ("ballast", "Ballast"),
        ("sailAreaUp", "Sail Area (up)"), ("sailAreaDown", "Sail Area (down)"),
        ("mainHoist", "Main Hoist"), ("mainFoot", "Main Foot"),
        ("headsailHoist", "Headsail Hoist"), ("overlap", "Overlap"),
        ("spinHoist", "Spinnaker Hoist"), ("spinPole", "Spinnaker Pole")
    ]
    for key, label in spec_fields:
        val = specs.get(key)
        formatted = spec_cell(val)
        if formatted:
            spec_rows.append((label, formatted))

    # Additional details
    if boat.get("rigType"):
        spec_rows.append(("Rig Type", esc(boat["rigType"])))
    if boat.get("rigMaterial"):
        spec_rows.append(("Rig Material", esc(boat["rigMaterial"])))
    if boat.get("keelType"):
        spec_rows.append(("Keel Type", esc(boat["keelType"])))
    if boat.get("hullConstruction"):
        spec_rows.append(("Hull Construction", esc(boat["hullConstruction"])))
    if boat.get("builder"):
        spec_rows.append(("Builder", esc(boat["builder"])))
    if boat.get("owner"):
        spec_rows.append(("Owner", esc(boat["owner"])))
    hulls = boat.get("hullsBuilt")
    if hulls and hulls > 0:
        spec_rows.append(("Hulls Built", str(hulls)))

    spec_html = "\n".join(
        f'<tr><td>{label}</td><td>{value}</td></tr>'
        for label, value in spec_rows
    )

    # Breadcrumb
    breadcrumb_mid = ""
    if dec != "Unknown":
        breadcrumb_mid = f' &rsaquo; <a href="/portfolio.html#{dec}">{dec}</a>'

    # Plan section — tier-specific (Sprint 2)
    plan_section = build_plan_section(boat)

    # Build page content (inside <main>)
    content = f'''
    <div class="yacht-detail-layout">
      <div class="breadcrumb">
        <a href="/portfolio.html">Portfolio</a>{breadcrumb_mid} &rsaquo; {esc(display_name)}
      </div>
      <div class="yacht-detail-header">
        <div class="yacht-number">{number_html}</div>
        <h1>{esc(display_name)}</h1>
        {f'<div class="yacht-meta-line">{meta_line}</div>' if meta_line else ''}
      </div>
      <div class="yacht-detail-body">
        <div>
          <div class="yacht-detail-image" style="background-image:url('{image_url}')">
            {img_tbc}
          </div>
          <div style="margin-top:1.5rem;">
            <p style="color:var(--text-secondary);line-height:1.7;font-size:0.92rem;">{display_desc}</p>
          </div>
        </div>
        <div class="yacht-detail-sidebar">
          <table class="spec-table">
            <thead><tr><th>Specification</th><th>Value</th></tr></thead>
            <tbody>
              {spec_html}
            </tbody>
          </table>
          {plan_section}
        </div>
      </div>
    </div>
    <div class="cta-band" style="text-align:center;padding:3rem 2rem;">
      <p style="font-family:var(--font-heading);font-size:1.15rem;color:var(--text-primary);margin-bottom:0.5rem;">Interested in a Farr design?</p>
      <p style="color:var(--text-secondary);font-size:0.9rem;max-width:500px;margin:0.5rem auto 1.25rem;">Whether you&rsquo;re looking for plans, consulting, or a new project &mdash; let&rsquo;s talk.</p>
      <a href="/contact.html" class="hero-cta" style="text-decoration:none;">Get in Touch</a>
    </div>'''

    # Wrap in base template
    page_title = f"{esc(display_name)} &mdash; Farr Yacht Design"
    full_html = base_html.replace("{{ pageTitle }} &mdash; Farr Yacht Design", page_title)
    full_html = full_html.replace("{{ content | safe }}", content)
    full_html = full_html.replace("{% block head %}{% endblock %}", "")

    return full_html

# ─── Build portfolio page ───

def build_portfolio_page():
    """Generate portfolio.html with all boats grouped by decade, with tier badges."""
    by_decade = {}
    for boat in boats:
        dec = decade(boat.get("year"))
        by_decade.setdefault(dec, []).append(boat)

    sorted_decades = sorted(
        [d for d in by_decade.keys() if d != "Unknown"],
        reverse=True
    )
    if "Unknown" in by_decade:
        sorted_decades.append("Unknown")

    total = len(boats)

    content = f'''
    <div class="content-section" style="padding-top:2rem;">
      <h1 style="font-family:var(--font-heading);font-size:2.2rem;margin-bottom:0.5rem;">Portfolio</h1>
      <p style="color:var(--text-secondary);font-size:1rem;margin-bottom:2rem;">{total} designs spanning six decades of yacht design innovation.</p>

      <div style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-bottom:2.5rem;">
        {"".join(f'<a href="#d{d}" style="padding:0.4rem 1rem;border:1px solid var(--border);border-radius:99px;font-size:0.8rem;color:var(--text-secondary);text-decoration:none;">{d} ({len(by_decade[d])})</a>' for d in sorted_decades)}
      </div>
'''

    for dec_label in sorted_decades:
        dec_boats = sorted(by_decade[dec_label], key=lambda b: b.get("title", ""))
        content += f'''
      <div id="d{dec_label}" style="margin-bottom:3rem;">
        <h2 style="font-family:var(--font-heading);font-size:1.5rem;margin-bottom:1.25rem;padding-bottom:0.5rem;border-bottom:1px solid var(--border);">{dec_label}</h2>
        <div class="detail-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1.5rem;">
'''
        for boat in dec_boats:
            slug = boat.get("slug", "")
            name = boat.get("name") or boat.get("title", slug)
            year_str = str(int(boat["year"])) if boat.get("year") and isinstance(boat["year"], (int, float)) else ""
            categories = boat.get("category") or []
            cat = categories[0] if categories else ""
            specs_obj = boat.get("specs") or {}
            loa = specs_obj.get("loa", {}) if isinstance(specs_obj, dict) else {}
            loa_ft = loa.get("ft") if isinstance(loa, dict) else None

            # Check images.main first, then fall back to slug
            card_img_main = (boat.get("images") or {}).get("main", "")
            if card_img_main and card_img_main.lower() in existing_images:
                has_img = True
                img_url = f"/images/{card_img_main}"
            else:
                has_img = f"{slug}.jpg" in existing_images
                img_url = f"/images/{slug}.jpg"

            meta_parts = []
            if loa_ft:
                meta_parts.append(f"{loa_ft}&prime;")
            if cat:
                meta_parts.append(cat)
            if year_str:
                meta_parts.append(year_str)
            meta_str = " | ".join(meta_parts) if meta_parts else ""

            design_num = boat.get("designNumber", "")
            num_display = f"#{esc(design_num)}" if design_num else f"#{esc(boat.get('title', ''))}"

            # Tier dot: green = plans available (Tier 1 + card), amber = archive (Tier 2)
            plan_status = boat.get("planStatus", "coming_soon")
            if plan_status == "available":
                tier_dot = '<span style="width:7px;height:7px;border-radius:50%;background:#3dba72;flex-shrink:0;" title="Plans available"></span>'
            elif plan_status == "request_from_shed":
                tier_dot = '<span style="width:7px;height:7px;border-radius:50%;background:#d97706;flex-shrink:0;" title="Archive request"></span>'
            else:
                tier_dot = ''

            img_tbc = ""
            if not has_img:
                img_tbc = '<span class="img-tbc"><svg class="img-tbc-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/><circle cx="12" cy="14" r="3"/></svg><span class="img-tbc-label">Photo coming soon</span></span>'

            content += f'''
          <a href="/yacht/{slug}.html" class="yacht-card" style="text-decoration:none;">
            <div class="yacht-card-image" style="background-image:url('{img_url}')">
              {img_tbc}
            </div>
            <div class="yacht-card-body">
              <div style="display:flex;align-items:center;gap:0.4rem;">
                <div class="yacht-card-number">{num_display}</div>
                {tier_dot}
              </div>
              <div class="yacht-card-name">{esc(name)}</div>
              {f'<div class="yacht-card-meta">{meta_str}</div>' if meta_str else ''}
            </div>
          </a>'''

        content += '''
        </div>
      </div>'''

    content += '''
    </div>
    <div class="cta-band" style="text-align:center;padding:3rem 2rem;">
      <p style="font-family:var(--font-heading);font-size:1.15rem;color:var(--text-primary);margin-bottom:0.5rem;">Looking for something specific?</p>
      <p style="color:var(--text-secondary);font-size:0.9rem;max-width:500px;margin:0.5rem auto 1.25rem;">Get in touch and we&rsquo;ll help you find the right design.</p>
      <a href="/contact.html" class="hero-cta" style="text-decoration:none;">Get in Touch</a>
    </div>'''

    page_title = "Portfolio &mdash; Farr Yacht Design"
    full_html = base_html.replace("{{ pageTitle }} &mdash; Farr Yacht Design", page_title)
    full_html = full_html.replace("{{ content | safe }}", content)
    full_html = full_html.replace("{% block head %}{% endblock %}", "")

    return full_html

# ─── Build _redirects ───

def build_redirects():
    """Generate _redirects file mapping old Drupal paths to new yacht slugs."""
    lines = [
        "# Farr Yacht Design - Redirects",
        "# Generated by build_site.py",
        "",
        "# Trailing slash normalization",
        "/*/ /:splat 301",
        "",
        "# Legacy Drupal aliases to new yacht pages",
    ]

    for boat in boats:
        slug = boat.get("slug", "")
        alias = boat.get("drupalAlias", "")
        nid = boat.get("nid")

        if alias:
            lines.append(f"/{alias} /yacht/{slug}.html 301")
        if nid:
            lines.append(f"/node/{nid} /yacht/{slug}.html 301")

    lines.append("")
    lines.append("# Legacy numbered HTML pages")
    for boat in boats:
        title = boat.get("title", "")
        slug = boat.get("slug", "")
        if re.match(r'^\d+[mM]?$', title):
            lines.append(f"/{title}.html /yacht/{slug}.html 301")
        # Also handle underscore variants (e.g., 92_2 → was 92/2)
        if '_' in title and re.match(r'^\d+_', title):
            lines.append(f"/{title}.html /yacht/{slug}.html 301")

    return "\n".join(lines) + "\n"

# ─── Build design-plans hub page (Sprint 2.5) ───

def build_design_plans_page():
    """Generate design-plans.html with filterable grid showing all designs grouped by plan status."""
    # Build JSON data for client-side filtering
    plans_data = []
    for boat in boats:
        name = boat.get("name") or boat.get("title", "")
        plans_data.append({
            "slug": boat.get("slug", ""),
            "dn": boat.get("designNumber", ""),
            "name": str(name) if name else "",
            "year": boat.get("year"),
            "tier": boat.get("tier", 3),
            "status": boat.get("planStatus", "coming_soon"),
            "dwgs": boat.get("cardDrawingCount"),
            "cat": (boat.get("category") or [""])[0] if boat.get("category") else "",
        })

    plans_json = json.dumps(plans_data, ensure_ascii=False)

    # Build the main content (same as yacht/portfolio pages — use base_html template)
    content = '''

    <div class="feature-hero">
      <div class="feature-hero-inner">
        <p class="section-label">Design Plans</p>
        <h1>Original Farr Design Plans</h1>
        <p class="hero-sub">Purchase and download original design drawings from the Farr Yacht Design archive &mdash; sail plans, lines drawings, deck layouts, and rig specifications spanning six decades.</p>
      </div>
    </div>

    <section class="content-section" style="background:var(--farr-mid);border-top:1px solid var(--border);border-bottom:1px solid var(--border);">
      <div class="section-inner">
        <p class="section-label">How It Works</p>
        <h2>Three Steps to Your Plans</h2>
        <div class="ecom-steps">
          <div class="ecom-step">
            <div class="ecom-step-num">Step 01</div>
            <div class="ecom-step-label">Find Your Design</div>
            <div class="ecom-step-body">Browse the catalog below. Plans marked <strong>Available</strong> are ready for immediate purchase and download.</div>
          </div>
          <div class="ecom-step">
            <div class="ecom-step-num">Step 02</div>
            <div class="ecom-step-label">Secure Checkout</div>
            <div class="ecom-step-body">Pay via card through our secure Stripe checkout. No account required. Receipt emailed immediately.</div>
          </div>
          <div class="ecom-step">
            <div class="ecom-step-num">Step 03</div>
            <div class="ecom-step-label">Instant Download</div>
            <div class="ecom-step-body">Download your plan set as a high-resolution PDF. Your link is valid for 48&nbsp;hours and stays in your confirmation email.</div>
          </div>
          <div class="ecom-step">
            <div class="ecom-step-num">Not Listed?</div>
            <div class="ecom-step-label">Request from the Archive</div>
            <div class="ecom-step-body">Designs marked <strong>Archive</strong> have physical drawings in Annapolis. Submit a request and we&rsquo;ll check availability.</div>
          </div>
        </div>
      </div>
    </section>

    <section class="content-section">
      <div class="section-inner">

        <!-- Filters -->
        <div style="display:flex;flex-wrap:wrap;gap:1rem;align-items:center;margin-bottom:2rem;">
          <div style="flex:1;min-width:200px;">
            <input type="text" id="dp-search" placeholder="Search by design number or name&hellip;" style="width:100%;padding:0.6rem 1rem;border:1px solid var(--border);border-radius:8px;background:var(--panel);color:var(--text-primary);font-size:0.88rem;">
          </div>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap;" id="dp-filters">
            <button class="dp-filter-btn dp-filter-active" data-filter="all">All <span id="dp-count-all"></span></button>
            <button class="dp-filter-btn" data-filter="available">Available <span id="dp-count-available"></span></button>
            <button class="dp-filter-btn" data-filter="request_from_shed">Archive <span id="dp-count-archive"></span></button>
            <button class="dp-filter-btn" data-filter="not_digitized">Digitizing <span id="dp-count-digitizing"></span></button>
          </div>
        </div>

        <!-- Results count -->
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem;" id="dp-results"></p>

        <!-- Plans grid -->
        <div class="plans-grid" id="dp-grid" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr));"></div>

      </div>
    </section>

    <section class="content-section" style="background:var(--farr-mid);border-top:1px solid var(--border);border-bottom:1px solid var(--border);">
      <div class="section-inner">
        <div class="waitlist-panel" id="waitlist-panel">
          <p class="section-label">Don&rsquo;t See Your Design?</p>
          <h2>Request a Design</h2>
          <p style="color:var(--text-secondary);font-size:0.92rem;line-height:1.7;max-width:560px;">Farr Yacht Design has drawn more than 900 designs since 1969. If the plan you need isn&rsquo;t listed, tell us what you&rsquo;re looking for. We&rsquo;ll search the archive and let you know what&rsquo;s available.</p>
          <form
            class="waitlist-form"
            id="waitlist-form"
            name="design-request"
            method="POST"
            data-netlify="true"
            netlify-honeypot="bot-field">
            <input type="hidden" name="form-name" value="design-request">
            <p style="display:none;"><label>Don&rsquo;t fill this out: <input name="bot-field"></label></p>
            <div class="waitlist-row">
              <div class="waitlist-field">
                <label for="req-name">Your Name</label>
                <input type="text" id="req-name" name="name" required placeholder="Jane Smith">
              </div>
              <div class="waitlist-field">
                <label for="req-email">Email Address</label>
                <input type="email" id="req-email" name="email" required placeholder="jane@example.com">
              </div>
            </div>
            <div class="waitlist-field">
              <label for="req-design">Design Name or Number</label>
              <input type="text" id="req-design" name="design" required placeholder="e.g. Farr 30, D.280, or hull number">
            </div>
            <div class="waitlist-field">
              <label for="req-use">Intended Use</label>
              <select id="req-use" name="use">
                <option value="">Select&hellip;</option>
                <option value="restoration">Boat restoration / refit</option>
                <option value="research">Historical research</option>
                <option value="replica">Replica build</option>
                <option value="class-racing">Class racing reference</option>
                <option value="other">Other</option>
              </select>
            </div>
            <button type="submit" class="btn-buy" style="align-self:flex-start;">Submit Request</button>
            <div class="waitlist-success" id="waitlist-success" role="alert">&#10003;&nbsp; Request received. We&rsquo;ll be in touch within 2&ndash;3 business days.</div>
          </form>
        </div>
      </div>
    </section>

    <section class="content-section">
      <div class="section-inner">
        <div class="callout-box">
          <p class="section-label">About the Archive</p>
          <h3>Over 900 Designs Since 1969</h3>
          <p>The Farr Yacht Design archive spans the full history of the studio &mdash; from early production one-designs to America&rsquo;s Cup campaigns, ocean racers, and superyachts. Original drawings are held in Annapolis. Digitization is an ongoing program; new plan sets are added regularly. All plans are sold for personal use only. Commercial use or reproduction requires a separate licensing agreement &mdash; <a href="contact.html">contact us</a> to discuss.</p>
        </div>
      </div>
    </section>

'''

    # Build the page-specific script block
    dp_script = '''
  <script>
    /* ── Design Plans Hub: client-side filtering ── */
    var ALL_PLANS = ''' + plans_json + ''';

    var currentFilter = 'all';
    var searchTerm = '';

    function escHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

    function statusBadge(status) {
      if (status === 'available') return '<span class="plan-badge plan-badge--available">Available</span>';
      if (status === 'request_from_shed') return '<span class="plan-badge" style="color:#d97706;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);display:inline-flex;align-items:center;font-family:var(--font-mono);font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;padding:0.25rem 0.65rem;border-radius:100px;">Archive</span>';
      if (status === 'not_digitized') return '<span class="plan-badge plan-badge--digitizing">Digitizing</span>';
      return '<span class="plan-badge" style="color:var(--text-muted);background:rgba(85,96,112,0.08);border:1px solid rgba(85,96,112,0.2);display:inline-flex;align-items:center;font-family:var(--font-mono);font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;padding:0.25rem 0.65rem;border-radius:100px;">Coming Soon</span>';
    }

    function statusLabel(status) {
      if (status === 'available') return 'Purchase Plan Set';
      if (status === 'request_from_shed') return 'Request This Plan';
      if (status === 'not_digitized') return 'Join Waitlist';
      return '';
    }

    function statusClass(status) {
      if (status === 'available') return 'plan-card--available';
      if (status === 'request_from_shed') return '';
      return 'plan-card--digitizing';
    }

    function renderHub() {
      var filtered = ALL_PLANS.filter(function(p) {
        if (currentFilter !== 'all' && p.status !== currentFilter) return false;
        if (searchTerm) {
          var q = searchTerm.toLowerCase();
          var dn = String(p.dn).toLowerCase();
          var nm = String(p.name).toLowerCase();
          if (dn.indexOf(q) === -1 && nm.indexOf(q) === -1) return false;
        }
        return true;
      });

      // Update counts
      var cAll = ALL_PLANS.length;
      var cAvail = ALL_PLANS.filter(function(p){return p.status==='available';}).length;
      var cArchive = ALL_PLANS.filter(function(p){return p.status==='request_from_shed';}).length;
      var cDigit = ALL_PLANS.filter(function(p){return p.status==='not_digitized';}).length;
      document.getElementById('dp-count-all').textContent = '('+cAll+')';
      document.getElementById('dp-count-available').textContent = '('+cAvail+')';
      document.getElementById('dp-count-archive').textContent = '('+cArchive+')';
      document.getElementById('dp-count-digitizing').textContent = '('+cDigit+')';

      document.getElementById('dp-results').textContent = filtered.length + ' design' + (filtered.length!==1?'s':'') + ' found';

      var grid = document.getElementById('dp-grid');
      if (filtered.length === 0) {
        grid.innerHTML = '<p style="color:var(--text-muted);font-size:0.88rem;grid-column:1/-1;">No designs match your search. Try a different term or <a href="#waitlist-panel">submit a request</a>.</p>';
        return;
      }

      grid.innerHTML = filtered.map(function(p) {
        var badge = statusBadge(p.status);
        var yearStr = p.year ? ' &middot; ' + p.year : '';
        var catStr = p.cat ? '<div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.25rem;">' + escHtml(p.cat) + '</div>' : '';
        var dwgStr = p.dwgs ? '<div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.35rem;">' + p.dwgs + ' drawings</div>' : '';
        var action = '';
        if (p.status === 'available') {
          action = '<a href="/yacht/'+p.slug+'.html" class="btn-buy" style="font-size:0.78rem;padding:0.5rem 1rem;text-decoration:none;">View Plans</a>';
        } else if (p.status === 'request_from_shed') {
          action = '<a href="#waitlist-form" class="btn-waitlist" style="font-size:0.78rem;padding:0.5rem 1rem;text-decoration:none;color:#d97706;border-color:#d97706;" onclick="prefillDesign(\\''+escHtml(p.dn)+'\\')">Request</a>';
        } else if (p.status === 'not_digitized') {
          action = '<a href="#waitlist-form" class="btn-waitlist" style="font-size:0.78rem;padding:0.5rem 1rem;text-decoration:none;" onclick="prefillDesign(\\''+escHtml(p.dn)+'\\')">Waitlist</a>';
        }

        return '<div class="plan-card '+statusClass(p.status)+'" style="padding:1.25rem;">'
          +'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;">'
          +'<div><span style="font-family:var(--font-mono);font-size:0.78rem;color:var(--text-muted);">#'+escHtml(p.dn)+'</span>'+yearStr+'</div>'
          +badge+'</div>'
          +'<div style="font-weight:600;font-size:0.92rem;color:var(--text-primary);margin-bottom:0.25rem;">'+escHtml(p.name || 'Design '+p.dn)+'</div>'
          +catStr+dwgStr
          +'<div style="margin-top:0.75rem;">'+action+'</div>'
          +'</div>';
      }).join('');
    }

    function prefillDesign(dn) {
      var f = document.getElementById('req-design');
      if (f) f.value = 'D.' + dn;
    }

    // Filter buttons
    document.querySelectorAll('.dp-filter-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        currentFilter = this.dataset.filter;
        document.querySelectorAll('.dp-filter-btn').forEach(function(b){b.classList.remove('dp-filter-active');});
        this.classList.add('dp-filter-active');
        renderHub();
      });
    });

    // Search
    document.getElementById('dp-search').addEventListener('input', function() {
      searchTerm = this.value;
      renderHub();
    });

    // Handle ?design=XXX query param
    var params = new URLSearchParams(window.location.search);
    var designParam = params.get('design');
    if (designParam) {
      document.getElementById('dp-search').value = designParam;
      searchTerm = designParam;
    }

    // Boot
    renderHub();

    /* ── Waitlist form ── */
    var wForm = document.getElementById('waitlist-form');
    if (wForm) {
      wForm.addEventListener('submit', function(e){
        e.preventDefault();
        var submitBtn = wForm.querySelector('button[type="submit"]');
        if (submitBtn) { submitBtn.textContent = 'Submitting\\u2026'; submitBtn.disabled = true; }
        fetch('/', {method:'POST', body: new FormData(wForm)})
          .then(function(r){
            if (!r.ok) throw new Error('Form submission failed');
            wForm.style.display='none';
            document.getElementById('waitlist-success').classList.add('visible');
          })
          .catch(function(){
            fetch('/.netlify/functions/join-waitlist', {
              method:'POST',
              headers:{'Content-Type':'application/json'},
              body: JSON.stringify({
                name: wForm.querySelector('[name="name"]').value,
                email: wForm.querySelector('[name="email"]').value,
                design: wForm.querySelector('[name="design"]').value,
                use: wForm.querySelector('[name="use"]').value
              })
            })
            .then(function(r){ return r.json(); })
            .then(function(result){
              if (result.success) {
                wForm.style.display='none';
                document.getElementById('waitlist-success').classList.add('visible');
              } else {
                alert('Submission failed. Please email plans@farrdesign.com');
                if (submitBtn) { submitBtn.textContent = 'Submit Request'; submitBtn.disabled = false; }
              }
            })
            .catch(function(){
              alert('Submission failed. Please email plans@farrdesign.com');
              if (submitBtn) { submitBtn.textContent = 'Submit Request'; submitBtn.disabled = false; }
            });
          });
      });
    }

    /* ── Handle ?cancelled=1 from Stripe ── */
    if (params.get('cancelled') === '1') {
      var banner = document.createElement('div');
      banner.setAttribute('role', 'alert');
      banner.style.cssText = 'background:#fef3c7;border:1px solid #f59e0b;color:#92400e;padding:0.75rem 1.25rem;font-size:0.85rem;text-align:center;';
      banner.textContent = 'Checkout was cancelled. Your card was not charged. Browse the catalog below to try again.';
      var main = document.getElementById('main');
      if (main && main.firstChild) main.insertBefore(banner, main.firstChild);
      history.replaceState(null, '', 'design-plans.html');
    }
  </script>'''

    # Use base template (same as yacht/portfolio pages)
    page_title = "Design Plans &mdash; Farr Yacht Design"
    full_html = base_html.replace("{{ pageTitle }} &mdash; Farr Yacht Design", page_title)
    full_html = full_html.replace("{{ content | safe }}", content)
    full_html = full_html.replace("{% block head %}{% endblock %}", "")

    # Inject the design-plans script before </body>
    full_html = full_html.replace("</body>", dp_script + "\n</body>")

    return full_html


# ─── Load base template ───

# Try to load base template; if not found, build pages without wrapping
base_template_path = os.path.join(WWW, "_includes", "base.njk")
if os.path.exists(base_template_path):
    with open(base_template_path) as f:
        base_html = f.read()
else:
    # Fall back: read from an existing yacht page and extract the template
    sample_page = os.path.join(WWW, "yacht", "720.html")
    if os.path.exists(sample_page):
        with open(sample_page) as f:
            base_html = f.read()
        # Create a template by replacing content
        base_html = re.sub(
            r'(<main id="main">).*?(</main>)',
            r'\1\n{{ content | safe }}\n\2',
            base_html,
            flags=re.DOTALL
        )
        base_html = re.sub(
            r'<title>.*?</title>',
            '<title>{{ pageTitle }} &mdash; Farr Yacht Design</title>',
            base_html
        )
    else:
        print("WARNING: No base template found. Yacht pages will be minimal.")
        base_html = '<!DOCTYPE html><html><head><title>{{ pageTitle }} &mdash; Farr Yacht Design</title></head><body><main id="main">{{ content | safe }}</main></body></html>'

print(f"Base template loaded ({len(base_html)} chars)")

# ─── Execute build ───

print("Building site...")

# www/ IS the deploy root — no clean/copy step needed.
# We only overwrite generated files (yacht pages, portfolio, design-plans, _redirects).

# 1. Generate yacht detail pages
yacht_dir = os.path.join(SITE, "yacht")
os.makedirs(yacht_dir, exist_ok=True)

generated = 0
errors = 0
for boat in boats:
    slug = boat.get("slug", "")
    if not slug:
        continue
    try:
        page_html = build_yacht_page(boat)
        out_path = os.path.join(yacht_dir, f"{slug}.html")
        with open(out_path, "w") as f:
            f.write(page_html)
        generated += 1
    except Exception as e:
        print(f"ERROR generating {slug}: {e}")
        errors += 1

print(f"Generated {generated} yacht pages ({errors} errors)")

# 4. Generate portfolio page
portfolio_html = build_portfolio_page()
with open(os.path.join(SITE, "portfolio.html"), "w") as f:
    f.write(portfolio_html)
print("Generated portfolio.html")

# 5. Generate design-plans hub page (Sprint 2.5)
dp_html = build_design_plans_page()
with open(os.path.join(SITE, "design-plans.html"), "w") as f:
    f.write(dp_html)
print("Generated design-plans.html (hub page with tier filtering)")

# 6. Generate _redirects
redirects = build_redirects()
with open(os.path.join(SITE, "_redirects"), "w") as f:
    f.write(redirects)
print(f"Generated _redirects ({redirects.count(chr(10))} rules)")

# 7. Update netlify.toml
netlify_toml_path = os.path.join(SITE, "netlify.toml")
if os.path.exists(netlify_toml_path):
    with open(netlify_toml_path) as f:
        toml_content = f.read()
    toml_content = toml_content.replace('publish = "."', 'publish = "."')
    with open(netlify_toml_path, "w") as f:
        f.write(toml_content)

# ─── Summary ───

total_files = sum(1 for _, _, files in os.walk(SITE) for _ in files)
yacht_pages = len([f for f in os.listdir(yacht_dir) if f.endswith('.html')])

# Tier stats
tier_stats = {}
status_stats = {}
for b in boats:
    t = b.get('tier', 0)
    s = b.get('planStatus', 'unknown')
    tier_stats[t] = tier_stats.get(t, 0) + 1
    status_stats[s] = status_stats.get(s, 0) + 1

print(f"\n{'='*50}")
print(f"BUILD COMPLETE")
print(f"{'='*50}")
print(f"Output directory: {SITE}")
print(f"Total files: {total_files}")
print(f"Yacht pages: {yacht_pages}")
print(f"Static pages: {total_files - yacht_pages} (passthrough)")
print(f"_redirects rules: {redirects.count(chr(10))}")
print(f"\nTier distribution:")
for t in sorted(tier_stats.keys()):
    print(f"  Tier {t}: {tier_stats[t]}")
print(f"Plan status distribution:")
for s, c in sorted(status_stats.items()):
    print(f"  {s}: {c}")
