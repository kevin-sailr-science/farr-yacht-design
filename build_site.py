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
SITE_URL = "https://farr-designs.sailr.science"

# ─── Load data ───

with open(DATA) as f:
    all_boats = json.load(f)

# Filter out hidden designs (display=N in Britt's spreadsheet)
boats = [b for b in all_boats if not b.get("hidden")]

print(f"Loaded {len(all_boats)} boats from boats.json ({len(boats)} visible, {len(all_boats)-len(boats)} hidden)")

# ─── Generate plan_catalog.json for checkout function (Sprint 5C) ───

plan_catalog = {}
for boat in all_boats:
    plan_id = boat.get('planId')
    if plan_id and boat.get('planStatus') == 'available':
        plan_catalog[plan_id] = {
            'designNumber': boat.get('designNumber'),
            'name': f"{boat.get('name') or boat.get('title', '')} — Full Plan Set",
            'stripePriceId': boat.get('stripePriceId', ''),
            'price': boat.get('planPrice'),
            'description': boat.get('planDescription', ''),
            'planContents': boat.get('planContents', ''),
        }

plan_catalog_path = os.path.join(SCRIPT_DIR, "_data", "plan_catalog.json")
with open(plan_catalog_path, 'w') as f:
    json.dump(plan_catalog, f, indent=2, ensure_ascii=False)
print(f"Generated plan_catalog.json ({len(plan_catalog)} purchasable plans)")

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

def _fmt_num(v):
    """Round a numeric value to 2 decimals; drop trailing zeros."""
    if v is None:
        return None
    r = round(float(v), 2)
    return int(r) if r == int(r) else r

def spec_cell(spec_obj):
    """Format a spec value with both imperial and metric units."""
    if not spec_obj or not isinstance(spec_obj, dict):
        return None
    parts = []
    ft = _fmt_num(spec_obj.get('ft'))
    m = _fmt_num(spec_obj.get('m'))
    lbs = spec_obj.get('lbs')
    kg = spec_obj.get('kg')
    sqft = _fmt_num(spec_obj.get('sqft'))
    sqm = _fmt_num(spec_obj.get('sqm'))
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

# ─── Image resolution cascade (Sprint IMG-41) ───

def resolve_image(boat, context="hero"):
    """Resolve the image URL for a boat in any context.

    Context: "hero" (detail page, OG tags), "card" (portfolio/feature cards)
    Returns: dict with keys: url, has_image, crop_hint, alt
    """
    images = boat.get("images") or {}
    slug = boat.get("slug", "")
    name = boat.get("name", "") or boat.get("title", "") or ""
    design_type = boat.get("designType", "") or ""

    # Resolution cascade
    img_file = None
    if context == "card" and images.get("card"):
        img_file = images["card"]
    if not img_file and images.get("hero"):
        img_file = images["hero"]

    has_image = False
    image_url = f"/images/{slug}.jpg"

    if img_file and img_file.lower() in existing_images:
        has_image = True
        image_url = f"/images/{img_file}"
    else:
        # Slug-based fallback
        for ext in [".webp", ".jpg", ".jpeg", ".png", ".gif"]:
            if f"{slug}{ext}" in existing_images:
                has_image = True
                image_url = f"/images/{slug}{ext}"
                break

    # Crop hint
    if context == "card" and images.get("cardCropHint"):
        crop_hint = images["cardCropHint"]
    elif images.get("cropHint"):
        crop_hint = images["cropHint"]
    else:
        crop_hint = ""

    # Alt text
    alt = images.get("alt") or ""
    if not alt and name:
        alt = str(name)
        if design_type:
            alt += f" {str(design_type).lower()}"

    return {
        "url": image_url,
        "has_image": has_image,
        "crop_hint": crop_hint,
        "alt": alt,
    }

# ─── Tier-specific plan section HTML ───

def build_plan_section(boat):
    """Generate the plan section HTML based on boats.json plan fields.

    Single purchase path: if planId + planPrice exist → Stripe checkout.
    Everything else is a non-purchase state (waitlist / archive / coming soon).
    Concept designs have no plans to sell — skip entirely.
    """
    # Concept designs have no drawings to digitize or sell
    design_type = boat.get("designType", "")
    tags = boat.get("tags", [])
    if design_type == "Concept" or "Concept" in tags:
        return ""

    design_num = boat.get("designNumber", "")
    plan_id = boat.get("planId")
    plan_price = boat.get("planPrice")
    plan_desc = boat.get("planDescription", "")
    plan_contents = boat.get("planContents", "")
    plan_status = boat.get("planStatus", "coming_soon")
    drawing_count = boat.get("cardDrawingCount")
    drawings_available = boat.get("cardDrawingsAvailable")
    tier = boat.get("tier", 3)

    # ─── PURCHASABLE: planId + planPrice in boats.json → Stripe checkout ───
    if plan_id and plan_price:
        drawing_info = ""
        if drawing_count:
            drawing_info = f'<p style="font-size:0.82rem;color:var(--text-muted);margin:0.5rem 0 0;">{drawing_count} original drawings in this plan set'
            if drawings_available and drawings_available != drawing_count:
                drawing_info += f' ({drawings_available} available)'
            drawing_info += '</p>'

        desc_html = f'<p style="font-size:0.88rem;color:var(--text-secondary);line-height:1.6;margin-bottom:0.75rem;">{esc(plan_desc)}</p>' if plan_desc else '<p style="font-size:0.88rem;color:var(--text-secondary);line-height:1.6;margin-bottom:0.75rem;">Original design drawings from the Farr archive available as PDF download.</p>'

        contents_html = ""
        if plan_contents:
            contents_html = f'''
            <details style="margin:0.5rem 0 0.75rem;font-size:0.84rem;">
              <summary style="cursor:pointer;color:var(--text-secondary);font-weight:500;">What&rsquo;s included</summary>
              <p style="margin:0.5rem 0 0;color:var(--text-muted);line-height:1.6;">{esc(plan_contents)}</p>
            </details>'''

        return f'''
          <div class="purchase-card">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
              <h3 style="margin:0;">Design Plans</h3>
              <span class="availability-badge availability-badge--available">Available</span>
            </div>
            {desc_html}
            {contents_html}
            {drawing_info}
            <div style="margin-top:1rem;">
              <button class="btn-purchase" onclick="initCheckout('{esc(plan_id)}')">Purchase &amp; Download &mdash; ${plan_price}</button>
            </div>
          </div>'''

    # ─── SCANNED PLANS: individual PDFs available for browsing/purchase ───
    plan_files = boat.get("planFiles", [])
    misc_files = boat.get("miscFiles", [])
    if plan_status == "scanned_available" and (plan_files or misc_files):
        slug = boat.get("slug", design_num)
        # Drawing list
        drawings_html = ""
        if plan_files:
            items = ""
            for pf in plan_files:
                fname = pf.get("filename", "")
                label = pf.get("label", fname)
                href = f"/plans/{design_num.zfill(3)}/{fname}"
                items += f'''
                <li style="display:flex;align-items:center;gap:0.5rem;padding:0.5rem 0;border-bottom:1px solid var(--border);">
                  <span style="font-size:0.85rem;color:var(--text-secondary);flex:1;">{esc(label)}</span>
                  <a href="{href}" target="_blank" style="font-size:0.75rem;color:var(--accent);white-space:nowrap;">View PDF</a>
                </li>'''
            drawings_html = f'''
            <div style="margin-top:0.75rem;">
              <p style="font-size:0.82rem;color:var(--text-muted);font-weight:500;margin-bottom:0.25rem;">{len(plan_files)} drawings available</p>
              <ul style="list-style:none;padding:0;margin:0;">{items}
              </ul>
            </div>'''

        # Free misc downloads
        misc_html = ""
        if misc_files:
            misc_items = ""
            for mf in misc_files:
                fname = mf.get("filename", "")
                label = mf.get("label", fname)
                href = f"/plans/{design_num.zfill(3)}/{fname}"
                misc_items += f'''
                <li style="display:flex;align-items:center;gap:0.5rem;padding:0.4rem 0;border-bottom:1px solid var(--border);">
                  <span style="font-size:0.85rem;color:var(--text-secondary);flex:1;">{esc(label)}</span>
                  <a href="{href}" target="_blank" style="font-size:0.75rem;color:#3dba72;white-space:nowrap;">Free Download</a>
                </li>'''
            misc_html = f'''
            <div style="margin-top:1.25rem;padding-top:1rem;border-top:2px solid var(--border);">
              <p style="font-size:0.82rem;color:var(--text-muted);font-weight:500;margin-bottom:0.25rem;">Free Downloads</p>
              <ul style="list-style:none;padding:0;margin:0;">{misc_items}
              </ul>
            </div>'''

        # Purchase button (price TBD — placeholder until Britt sets pricing)
        purchase_html = ""
        if plan_id and plan_price:
            purchase_html = f'''
            <div style="margin-top:1rem;">
              <button class="btn-purchase" onclick="initCheckout('{esc(plan_id)}')">Purchase Full Plan Set &mdash; ${plan_price}</button>
            </div>'''

        return f'''
          <div class="purchase-card">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
              <h3 style="margin:0;">Design Plans</h3>
              <span class="availability-badge availability-badge--available">Scanned Plans</span>
            </div>
            <p style="font-size:0.88rem;color:var(--text-secondary);line-height:1.6;margin-bottom:0.5rem;">Original scanned design drawings from the Farr archive.</p>
            {drawings_html}
            {misc_html}
            {purchase_html}
          </div>'''

    # ─── NOT YET DIGITIZED: waitlist ───
    if plan_status in ("coming_soon", "not_digitized"):
        return f'''
          <div class="purchase-card purchase-card--waitlist">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
              <h3 style="margin:0;">Design Plans</h3>
              <span class="availability-badge availability-badge--coming">Digitizing</span>
            </div>
            <p class="purchase-waitlist-note">Plans for this design have not yet been digitized. Join the waitlist and we&rsquo;ll notify you as soon as plans are available for download.</p>
            <button class="btn-waitlist" onclick="window.location.href='/design-plans.html?design={esc(design_num)}'">Join Waitlist</button>
          </div>'''

    # ─── PHYSICAL ARCHIVE: request from the shed ───
    if plan_status == "request_from_shed":
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

    # ─── FALLBACK: Coming Soon ───
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
    if design_type and design_type != design_rule and design_type != category:
        meta_parts.append(design_type)
    meta_line = " | ".join(meta_parts)
    if not meta_line and year:
        meta_line = dec
    if meta_line and year:
        meta_line += f" | {year}"

    # Image — resolve via cascade (Sprint IMG-41)
    img_resolved = resolve_image(boat, context="hero")
    has_image = img_resolved["has_image"]
    image_url = img_resolved["url"]
    crop_hint = img_resolved["crop_hint"]
    crop_style = f" background-position:{crop_hint};" if crop_hint else ""
    img_alt = img_resolved["alt"] or esc(display_name)

    img_tbc = ""
    if not has_image:
        img_tbc = '''<span class="img-tbc"><svg class="img-tbc-icon" viewBox="0 0 100 60" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 45 Q20 42 30 44 Q50 35 70 40 Q80 38 90 42 L90 50 Q80 48 70 49 Q50 47 30 50 Q20 49 10 50 Z" fill="currentColor" opacity="0.15"/><path d="M50 10 L50 38 M50 10 L75 30 Q65 28 55 32 Z" stroke="currentColor" stroke-width="1" fill="currentColor" opacity="0.12"/><path d="M50 10 L42 28 Q46 26 50 30" stroke="currentColor" stroke-width="0.8" fill="none" opacity="0.1"/></svg><span class="img-tbc-label">Photo coming soon</span></span>'''

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
    if design_type and design_type != design_rule and design_type != category:
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
    # Owner is admin-only (not public-facing per Britt's request)
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

    # Gallery images (Sprint IMG-43)
    images_data = boat.get("images") or {}
    gallery_files = images_data.get("gallery") or []
    gallery_items = []
    for gf in gallery_files:
        if gf and isinstance(gf, str) and gf.lower() in existing_images:
            galt = img_alt  # reuse hero alt as base
            gallery_items.append({"url": f"/images/{gf}", "alt": galt})
    # Build gallery HTML (thumbnail strip below hero)
    gallery_html = ""
    if gallery_items:
        thumbs = ""
        for i, gi in enumerate(gallery_items):
            thumbs += f'''<button class="gallery-thumb" onclick="swapHero('{gi["url"]}','{esc(gi["alt"])}')" aria-label="View photo {i+2}" style="background-image:url('{gi["url"]}');background-size:cover;background-position:center;"></button>\n'''
        gallery_html = f'''
          <div class="yacht-gallery" style="display:flex;gap:0.5rem;margin-top:0.75rem;overflow-x:auto;padding-bottom:0.5rem;">
            <button class="gallery-thumb gallery-thumb--active" onclick="swapHero('{image_url}','{esc(img_alt)}')" aria-label="View main photo" style="background-image:url('{image_url}');background-size:cover;background-position:center;{f'background-position:{crop_hint};' if crop_hint else ''}"></button>
            {thumbs}
          </div>'''

    # Build hero image as <picture> element (Sprint IMG-44)
    crop_pos = f"object-position:{crop_hint};" if crop_hint else "object-position:center 40%;"
    if has_image:
        # Check if WebP sibling exists
        webp_url = re.sub(r'\.(jpe?g|png)$', '.webp', image_url, flags=re.IGNORECASE)
        webp_file = webp_url.lstrip('/').split('/')[-1]
        has_webp = webp_file.lower() in existing_images
        webp_source = f'<source srcset="{webp_url}" type="image/webp">' if has_webp and webp_url != image_url else ""
        hero_img_html = f'''<picture>
              {webp_source}
              <img src="{image_url}" alt="{esc(img_alt)}" style="width:100%;height:100%;object-fit:cover;{crop_pos}" loading="eager">
            </picture>'''
        detail_img_click = f''' onclick="openLightbox('{image_url}','{esc(display_name)}')"'''
    else:
        hero_img_html = img_tbc
        detail_img_click = ""

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
          <div class="yacht-detail-image"{detail_img_click}>
            {hero_img_html}
          </div>{gallery_html}
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
    </div>
    <div class="yacht-lightbox" id="yachtLightbox" onclick="closeLightbox()">
      <button class="yacht-lightbox-close" aria-label="Close">&times;</button>
      <img id="lightboxImg" src="" alt="">
    </div>
    <script>
    function openLightbox(src,alt){{var lb=document.getElementById('yachtLightbox'),img=document.getElementById('lightboxImg');img.src=src;img.alt=alt;lb.classList.add('active');document.body.style.overflow='hidden';}}
    function closeLightbox(){{var lb=document.getElementById('yachtLightbox');lb.classList.remove('active');document.body.style.overflow='';}}
    function swapHero(src,alt){{var hero=document.querySelector('.yacht-detail-image');if(hero){{var img=hero.querySelector('img');if(img){{img.src=src;img.alt=alt;var source=hero.querySelector('source[type="image/webp"]');if(source)source.srcset=src.replace(/\\.(jpe?g|png)$/i,'.webp');}}hero.setAttribute('onclick',"openLightbox('"+src+"','"+alt+"')");}}document.querySelectorAll('.gallery-thumb').forEach(function(t){{t.classList.remove('gallery-thumb--active');}});if(event&&event.currentTarget)event.currentTarget.classList.add('gallery-thumb--active');}}
    document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeLightbox();}});
    </script>'''

    # Wrap in base template
    page_title = f"{esc(display_name)} &mdash; Farr Yacht Design"

    # OG meta tags for link previews (iMessage, WhatsApp, Slack, etc.)
    og_image_url = f"{SITE_URL}{image_url}" if has_image else f"{SITE_URL}/images/og-default.png"
    og_desc = display_desc[:200] if len(display_desc) > 200 else display_desc
    # Get actual image dimensions for OG tags (crawlers reject mismatched sizes)
    og_img_w, og_img_h = 1200, 630  # default for og-default.png
    if has_image:
        try:
            from PIL import Image as PILImage
            with PILImage.open(os.path.join(WWW, image_url.lstrip("/"))) as pil_img:
                og_img_w, og_img_h = pil_img.size
        except Exception:
            og_img_w, og_img_h = 0, 0  # omit dimensions if unreadable
    og_size_tags = ""
    if og_img_w and og_img_h:
        # Detect actual image content type from file extension
        og_ext = os.path.splitext(og_image_url)[1].lower()
        og_mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                       '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml'}
        og_content_type = og_mime_map.get(og_ext, 'image/jpeg')
        og_size_tags = f'''
  <meta property="og:image:width" content="{og_img_w}" />
  <meta property="og:image:height" content="{og_img_h}" />
  <meta property="og:image:type" content="{og_content_type}" />'''
    og_tags = f'''<meta name="description" content="{esc(og_desc)}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{SITE_URL}/yacht/{slug}.html" />
  <meta property="og:title" content="{esc(display_name)} — Farr Yacht Design" />
  <meta property="og:description" content="{esc(og_desc)}" />
  <meta property="og:image" content="{og_image_url}" />{og_size_tags}
  <meta name="twitter:card" content="summary_large_image" />'''

    full_html = base_html.replace("{{ pageTitle }} &mdash; Farr Yacht Design", page_title)
    full_html = full_html.replace("{{ content | safe }}", content)
    full_html = full_html.replace("{% block head %}{% endblock %}", og_tags)

    return full_html

# ─── Type consolidation mapping (Sprint 9) ───

TYPE_GROUPS = {
    'Racing': ['Racing Yacht', 'Racing', 'Racing Yacht (1 Ton)', 'Racing Yacht (Maxi)',
               'Grand Prix Racing Yacht', 'IRC Racing Yacht', 'Ocean Racer', 'Ocean Racing Yacht',
               'IMS Racer', 'ILC Racer', 'IMS Racing Yacht', 'ILC 40 Racer',
               'ILC Maxi', 'One Design IMS'],
    'Cruising': ['Cruising Yacht', 'Cruising Sloop', 'Fast Cruising Yacht', 'High Performance Cruiser',
                 'Fast Cruiser', 'Charter Yacht', 'Keel Yacht', 'Sailing Yacht', 'Yacht', 'Cruiser'],
    'Racer/Cruiser': ['Racing/Cruising', 'Cruiser/Racer', 'Racer/Cruiser', 'Racing/Cruising Yacht',
                      'Ocean Racer/Cruiser', 'Cruising/Racing Yacht', 'Production Cruiser-Racer',
                      'Production Cruiser/Racer', 'Production', 'IMS Cruiser/Racer',
                      'IMS Racer/Cruiser', 'IMS Racing/Cruising Yacht'],
    'One Design': ['One Design', 'One Design Racer', 'One-Design', 'One Design Racing Yacht'],
    'Offshore': ['Volvo Ocean Race', 'IMOCA Open 60', "America's Cup"],
    'Dinghy & Small': ['Dinghy', 'Trailer Sailer', 'Sharpie'],
    'Power': ['Powerboat', 'Power Yacht'],
    'Superyacht': ['Superyacht'],
    'Concept': ['Concept'],
    'Other': ['Multihull', 'Unknown', 'Tank Testing/Research', 'Other'],
}

# Build reverse lookup: raw type → group name
TYPE_TO_GROUP = {}
for group, raw_types in TYPE_GROUPS.items():
    for rt in raw_types:
        TYPE_TO_GROUP[rt] = group

def get_type_group(raw_type):
    """Map a raw designType to its consolidated group."""
    if not raw_type:
        return ''
    return TYPE_TO_GROUP.get(raw_type, 'Other')


# ─── Build portfolio page (Sprint 9: interactive sort/filter/views) ───

def build_portfolio_page():
    """Generate portfolio.html with client-side search, sort, filter, and grid/list views."""

    # Build JSON data for client-side interactivity
    portfolio_data = []
    for boat in boats:
        slug = boat.get("slug", "")
        name = boat.get("name") or boat.get("title", slug)
        year_val = boat.get("year")
        year_int = int(year_val) if year_val and isinstance(year_val, (int, float)) else 0
        year_str = str(year_int) if year_int else ""
        dec = decade(year_val)
        categories = boat.get("category") or []
        cat = categories[0] if categories else ""
        raw_type = boat.get("designType", "")
        type_group = get_type_group(raw_type)
        specs_obj = boat.get("specs") or {}
        loa = specs_obj.get("loa", {}) if isinstance(specs_obj, dict) else {}
        loa_ft = loa.get("ft") if isinstance(loa, dict) else None
        loa_m = loa.get("m") if isinstance(loa, dict) else None
        builder = boat.get("builder", "")
        design_num = boat.get("designNumber", "")
        tags = boat.get("tags", [])
        plan_status = boat.get("planStatus", "coming_soon")

        # Resolve image via cascade (Sprint IMG-41)
        card_resolved = resolve_image(boat, context="card")
        has_img = card_resolved["has_image"]
        img_url = card_resolved["url"]
        # Prefer WebP URL at build time (Sprint IMG-44)
        if has_img:
            webp_candidate = re.sub(r'\.(jpe?g|png)$', '.webp', img_url, flags=re.IGNORECASE)
            webp_fname = webp_candidate.split('/')[-1]
            if webp_fname.lower() in existing_images:
                img_url = webp_candidate

        # Numeric sort key for design number
        dn_num = 0
        if design_num:
            m = re.match(r'(\d+)', str(design_num))
            if m:
                dn_num = int(m.group(1))

        portfolio_data.append({
            's': slug,           # slug
            'n': str(name) if name else '',  # name
            'dn': str(design_num),  # design number
            'dnn': dn_num,       # design number numeric
            'y': year_int,       # year (int)
            'ys': year_str,      # year (string)
            'd': dec,            # decade
            'tg': type_group,    # type group (consolidated)
            'tr': raw_type,      # type raw
            'b': str(builder) if builder else '',  # builder
            'lf': loa_ft,        # LOA feet
            'lm': loa_m,         # LOA meters
            'hi': has_img,       # has image
            'iu': img_url,       # image url
            'ch': card_resolved["crop_hint"],  # cropHint
            'ps': plan_status,   # plan status
            'c': cat,            # category
            'tags': tags,        # tags (Production, Concept, Military, Commercial)
        })

    portfolio_json = json.dumps(portfolio_data, ensure_ascii=False, separators=(',', ':'))

    # Collect unique values for filter dropdowns
    type_groups_used = sorted(set(d['tg'] for d in portfolio_data if d['tg']))
    decades_list = sorted(set(d['d'] for d in portfolio_data if d['d'] != 'Unknown'), reverse=True)
    if any(d['d'] == 'Unknown' for d in portfolio_data):
        decades_list.append('Unknown')
    # Collect unique tags for filter dropdown
    tags_used = sorted(set(t for d in portfolio_data for t in d.get('tags', [])))

    total = len(boats)

    # Build type group options
    type_options = ''.join(f'<option value="{esc(tg)}">{esc(tg)}</option>' for tg in type_groups_used)
    decade_options = ''.join(f'<option value="{esc(d)}">{esc(d)}</option>' for d in decades_list)
    tag_options = ''.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in tags_used)

    # Pick featured design: most recent visible design with image and description
    featured_html = ''
    featured_candidates = sorted(
        [d for d in portfolio_data if d['hi'] and d['y'] > 0],
        key=lambda d: d['y'], reverse=True
    )
    if featured_candidates:
        import random
        # Use day-of-year as seed for daily rotation
        import datetime
        seed = datetime.date.today().timetuple().tm_yday
        random.seed(seed)
        pool = featured_candidates[:20]  # top 20 most recent with images
        fd = random.choice(pool)
        fd_boat = next((b for b in boats if b.get('slug') == fd['s']), None)
        fd_desc = ''
        if fd_boat:
            fd_desc = fd_boat.get('shortDescription') or ''
        featured_html = f'''
      <div style="margin-bottom:2rem;">
        <p class="section-label" style="margin-bottom:0.5rem;">Featured Design</p>
        <a href="/yacht/{esc(fd['s'])}.html" style="display:grid;grid-template-columns:280px 1fr;gap:1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden;text-decoration:none;transition:border-color 0.2s;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">
          <div style="background-image:url('{fd['iu']}');background-size:cover;background-position:center;min-height:180px;"></div>
          <div style="padding:1.25rem 1.25rem 1.25rem 0;display:flex;flex-direction:column;justify-content:center;">
            <div style="font-size:0.75rem;color:var(--accent);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.25rem;">#{esc(fd['dn'] or fd['s'])}</div>
            <div style="font-family:var(--font-heading);font-size:1.3rem;color:var(--text-primary);margin-bottom:0.4rem;">{esc(fd['n'])}</div>
            <div style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:0.5rem;">{esc(fd_desc)}</div>
            <div style="font-size:0.8rem;color:var(--text-muted);">{fd['ys']}{' | ' + esc(fd['tg']) if fd['tg'] else ''}</div>
          </div>
        </a>
      </div>'''

    content = f'''
    <div class="content-section" style="padding-top:2rem;">
      <h1 style="font-family:var(--font-heading);font-size:2.2rem;margin-bottom:0.5rem;">Portfolio</h1>
      <p style="color:var(--text-secondary);font-size:1rem;margin-bottom:1.5rem;">{total} designs spanning six decades of yacht design innovation.</p>

      {featured_html}

      <!-- Search -->
      <div class="pf-search-row">
        <input type="text" id="pf-search" placeholder="Search by name, design number, or builder\u2026" autocomplete="off" aria-label="Search designs" />
      </div>

      <!-- Controls bar -->
      <div class="pf-controls">
        <div class="pf-filters">
          <select id="pf-type" class="pf-select" aria-label="Filter by type"><option value="">All Types</option>{type_options}</select>
          <select id="pf-decade" class="pf-select" aria-label="Filter by decade"><option value="">All Decades</option>{decade_options}</select>
          <select id="pf-tag" class="pf-select" aria-label="Filter by tag"><option value="">All Tags</option>{tag_options}</select>
        </div>
        <div class="pf-right">
          <div class="pf-sort">
            <span class="pf-sort-label">Sort:</span>
            <button class="sort-btn active" data-sort="dn" data-dir="asc">Design #</button>
            <button class="sort-btn" data-sort="y" data-dir="desc">Year</button>
            <button class="sort-btn" data-sort="n" data-dir="asc">Name</button>
            <button class="sort-btn" data-sort="lf" data-dir="desc">Size</button>
          </div>
          <div class="pf-view-toggle">
            <button class="pf-view-btn active" data-view="grid" title="Grid view" aria-label="Grid view">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
            </button>
            <button class="pf-view-btn" data-view="list" title="List view" aria-label="List view">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><rect x="1" y="1" width="14" height="3" rx="1"/><rect x="1" y="6.5" width="14" height="3" rx="1"/><rect x="1" y="12" width="14" height="3" rx="1"/></svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Results count -->
      <div class="pf-status">
        <span id="pf-count" class="portfolio-count" aria-live="polite">{total} designs</span>
        <button id="pf-clear" class="pf-clear-btn" style="display:none;">Clear filters</button>
      </div>

      <!-- Grid container (cards rendered by JS) -->
      <div id="pf-grid" class="pf-grid"></div>

      <!-- List container (table rendered by JS) -->
      <div id="pf-list" class="pf-list" style="display:none;">
        <table class="pf-table">
          <thead>
            <tr>
              <th>Design #</th>
              <th>Name</th>
              <th>Year</th>
              <th>Type</th>
              <th class="pf-hide-mobile">LOA</th>
            </tr>
          </thead>
          <tbody id="pf-tbody"></tbody>
        </table>
      </div>

    </div>

    <div class="cta-band" style="text-align:center;padding:3rem 2rem;">
      <p style="font-family:var(--font-heading);font-size:1.15rem;color:var(--text-primary);margin-bottom:0.5rem;">Looking for something specific?</p>
      <p style="color:var(--text-secondary);font-size:0.9rem;max-width:500px;margin:0.5rem auto 1.25rem;">Get in touch and we&rsquo;ll help you find the right design.</p>
      <a href="/contact.html" class="hero-cta" style="text-decoration:none;">Get in Touch</a>
    </div>

    <script>
    (function() {{
      'use strict';
      var DATA = {portfolio_json};

      // ── State ──
      var state = {{
        sort: 'dn', dir: 'asc', view: 'grid',
        search: '', type: '', decade: '', tag: ''
      }};

      // ── DOM refs ──
      var $search = document.getElementById('pf-search');
      var $type = document.getElementById('pf-type');
      var $decade = document.getElementById('pf-decade');
      var $tag = document.getElementById('pf-tag');
      var $count = document.getElementById('pf-count');
      var $clear = document.getElementById('pf-clear');
      var $grid = document.getElementById('pf-grid');
      var $list = document.getElementById('pf-list');
      var $tbody = document.getElementById('pf-tbody');

      // ── Filter + Sort ──
      function filterAndSort() {{
        var q = state.search.toLowerCase();
        var filtered = DATA.filter(function(d) {{
          if (q && d.n.toLowerCase().indexOf(q) === -1 &&
              d.dn.toLowerCase().indexOf(q) === -1 &&
              d.b.toLowerCase().indexOf(q) === -1) return false;
          if (state.type && d.tg !== state.type) return false;
          if (state.decade && d.d !== state.decade) return false;
          if (state.tag && (!d.tags || d.tags.indexOf(state.tag) === -1)) return false;
          return true;
        }});

        var sortKey = state.sort;
        var dir = state.dir === 'asc' ? 1 : -1;
        filtered.sort(function(a, b) {{
          var va, vb;
          if (sortKey === 'dn') {{ va = a.dnn; vb = b.dnn; }}
          else if (sortKey === 'y') {{ va = a.y || 0; vb = b.y || 0; }}
          else if (sortKey === 'n') {{ va = (a.n || '').toLowerCase(); vb = (b.n || '').toLowerCase(); }}
          else if (sortKey === 'lf') {{ va = a.lf || 0; vb = b.lf || 0; }}
          else {{ va = a.dnn; vb = b.dnn; }}
          if (va < vb) return -1 * dir;
          if (va > vb) return 1 * dir;
          return 0;
        }});

        return filtered;
      }}

      // ── Render ──
      function escH(s) {{ var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}

      function renderGrid(items) {{
        var html = '';
        for (var i = 0; i < items.length; i++) {{
          var d = items[i];
          var numDisp = d.dn ? '#' + escH(d.dn) : '#' + escH(d.s);
          var meta = [];
          if (d.lf) meta.push(d.lf + '&prime;');
          if (d.c) meta.push(escH(d.c));
          if (d.ys) meta.push(d.ys);
          var metaStr = meta.join(' | ');
          var dot = '';
          if (d.ps === 'available' || d.ps === 'scanned_available') dot = '<span style="width:7px;height:7px;border-radius:50%;background:#3dba72;flex-shrink:0;" title="Plans available"></span>';
          else if (d.ps === 'request_from_shed') dot = '<span style="width:7px;height:7px;border-radius:50%;background:#d97706;flex-shrink:0;" title="Archive request"></span>';

          var imgAttr = d.hi ? ' data-bg="'+d.iu+'"'+(d.ch ? ' data-crop="'+d.ch+'"' : '')+' role="img" aria-label="'+escH(d.n)+'"' : '';
          var tbc = d.hi ? '' : '<span class="img-tbc"><svg class="img-tbc-icon" viewBox="0 0 100 60" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M10 45 Q20 42 30 44 Q50 35 70 40 Q80 38 90 42 L90 50 Q80 48 70 49 Q50 47 30 50 Q20 49 10 50 Z" fill="currentColor" opacity="0.15"/><path d="M50 10 L50 38 M50 10 L75 30 Q65 28 55 32 Z" stroke="currentColor" stroke-width="1" fill="currentColor" opacity="0.12"/><path d="M50 10 L42 28 Q46 26 50 30" stroke="currentColor" stroke-width="0.8" fill="none" opacity="0.1"/></svg><span class="img-tbc-label">Photo coming soon</span></span>';

          // Type tag overlay on card image
          var typeTag = '';
          if (d.tg) typeTag = '<span class="yacht-card-type-tag yacht-card-type-' + d.tg.toLowerCase().replace(/[^a-z]/g, '-') + '">' + escH(d.tg) + '</span>';

          // Improved title: "Type - Name" or just Name
          var titleText = d.n;
          if (d.tr && d.n && d.tr !== d.n && d.c !== d.tr) titleText = escH(d.tr) + ' - ' + escH(d.n);
          else titleText = escH(d.n);

          html += '<a href="/yacht/' + d.s + '.html" class="yacht-card" style="text-decoration:none;">' +
            '<div class="yacht-card-image"' + imgAttr + '>' + typeTag + tbc + '</div>' +
            '<div class="yacht-card-body">' +
              '<div style="display:flex;align-items:center;gap:0.4rem;">' +
                '<div class="yacht-card-number">' + numDisp + '</div>' + dot +
              '</div>' +
              '<div class="yacht-card-name">' + titleText + '</div>' +
              (metaStr ? '<div class="yacht-card-meta">' + metaStr + '</div>' : '') +
            '</div></a>';
        }}
        $grid.innerHTML = html;
      }}

      function renderList(items) {{
        var html = '';
        for (var i = 0; i < items.length; i++) {{
          var d = items[i];
          var loaStr = '';
          if (d.lf) loaStr = d.lf + ' ft';
          else if (d.lm) loaStr = d.lm + ' m';
          html += '<tr>' +
            '<td><a href="/yacht/' + d.s + '.html">' + escH(d.dn || d.s) + '</a></td>' +
            '<td><a href="/yacht/' + d.s + '.html">' + escH(d.n) + '</a></td>' +
            '<td>' + (d.ys || '') + '</td>' +
            '<td>' + escH(d.tg || d.tr) + '</td>' +
            '<td class="pf-hide-mobile">' + loaStr + '</td>' +
          '</tr>';
        }}
        $tbody.innerHTML = html;
      }}

      // Lazy-load background images via IntersectionObserver (Sprint 14D)
      // WebP URLs are now resolved at build time (Sprint IMG-44)

      var lazyObserver = ('IntersectionObserver' in window)
        ? new IntersectionObserver(function(entries) {{
            entries.forEach(function(entry) {{
              if (entry.isIntersecting) {{
                var el = entry.target;
                var bg = el.getAttribute('data-bg');
                if (bg) {{ el.style.backgroundImage = 'url(' + bg + ')'; var cp = el.getAttribute('data-crop'); if (cp) el.style.backgroundPosition = cp; el.removeAttribute('data-bg'); }}
                lazyObserver.unobserve(el);
              }}
            }});
          }}, {{ rootMargin: '200px 0px' }})
        : null;

      function observeLazy() {{
        if (!lazyObserver) {{
          // Fallback: load all images immediately
          $grid.querySelectorAll('[data-bg]').forEach(function(el) {{
            el.style.backgroundImage = 'url(' + el.getAttribute('data-bg') + ')';
            var cp = el.getAttribute('data-crop'); if (cp) el.style.backgroundPosition = cp;
            el.removeAttribute('data-bg');
          }});
          return;
        }}
        $grid.querySelectorAll('[data-bg]').forEach(function(el) {{ lazyObserver.observe(el); }});
      }}

      function render() {{
        var items = filterAndSort();
        $count.textContent = items.length + ' design' + (items.length !== 1 ? 's' : '');
        var hasFilters = state.search || state.type || state.decade || state.tag;
        $clear.style.display = hasFilters ? 'inline-block' : 'none';

        if (state.view === 'grid') {{
          $grid.style.display = '';
          $list.style.display = 'none';
          renderGrid(items);
          observeLazy();
        }} else {{
          $grid.style.display = 'none';
          $list.style.display = '';
          renderList(items);
        }}
      }}

      // ── Event handlers ──
      var debounceTimer;
      $search.addEventListener('input', function() {{
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function() {{
          state.search = $search.value.trim();
          render();
        }}, 200);
      }});

      $type.addEventListener('change', function() {{ state.type = this.value; render(); }});
      $decade.addEventListener('change', function() {{ state.decade = this.value; render(); }});
      $tag.addEventListener('change', function() {{ state.tag = this.value; render(); }});

      $clear.addEventListener('click', function() {{
        state.search = ''; state.type = ''; state.decade = ''; state.tag = '';
        $search.value = ''; $type.value = ''; $decade.value = ''; $tag.value = '';
        render();
      }});

      // Sort buttons
      document.querySelectorAll('.sort-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
          var key = this.getAttribute('data-sort');
          if (state.sort === key) {{
            state.dir = state.dir === 'asc' ? 'desc' : 'asc';
          }} else {{
            state.sort = key;
            state.dir = this.getAttribute('data-dir') || 'asc';
          }}
          document.querySelectorAll('.sort-btn').forEach(function(b) {{ b.classList.remove('active'); }});
          this.classList.add('active');
          // Update arrow indicator
          this.setAttribute('data-dir', state.dir);
          render();
        }});
      }});

      // View toggle
      document.querySelectorAll('.pf-view-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
          state.view = this.getAttribute('data-view');
          document.querySelectorAll('.pf-view-btn').forEach(function(b) {{ b.classList.remove('active'); }});
          this.classList.add('active');
          render();
        }});
      }});

      // Initial render
      render();
    }})();
    </script>
'''

    page_title = "Portfolio &mdash; Farr Yacht Design"
    full_html = base_html.replace("{{ pageTitle }} &mdash; Farr Yacht Design", page_title)
    full_html = full_html.replace("{{ content | safe }}", content)
    full_html = full_html.replace("{% block head %}{% endblock %}", "")

    return full_html

# ─── Build _redirects ───

def build_redirects():
    """Generate _redirects file for Netlify."""
    lines = [
        "# Farr Yacht Design - Redirects",
        "# Generated by build_site.py",
        "",
        "# Trailing slash normalization",
        "/*/ /:splat 301",
    ]

    return "\n".join(lines) + "\n"

# ─── Build design-plans hub page (Sprint 2.5) ───

def build_design_plans_page():
    """Generate design-plans.html with filterable grid showing all designs grouped by plan status."""
    # Build JSON data for client-side filtering
    plans_data = []
    for boat in boats:
        name = boat.get("name") or boat.get("title", "")
        entry = {
            "slug": boat.get("slug", ""),
            "dn": boat.get("designNumber", ""),
            "name": str(name) if name else "",
            "year": boat.get("year"),
            "tier": boat.get("tier", 3),
            "status": boat.get("planStatus", "coming_soon"),
            "dwgs": boat.get("cardDrawingCount"),
            "cat": (boat.get("category") or [""])[0] if boat.get("category") else "",
        }
        # Include e-commerce fields if present (Sprint 5C)
        if boat.get("planId"):
            entry["planId"] = boat["planId"]
        if boat.get("planPrice"):
            entry["price"] = boat["planPrice"]
        # Include scanned plan count (Sprint 11)
        if boat.get("planFiles"):
            entry["dwgs"] = len(boat["planFiles"])
        plans_data.append(entry)

    plans_json = json.dumps(plans_data, ensure_ascii=False)

    # Build the main content (same as yacht/portfolio pages — use base_html template)
    content = '''

    <div class="feature-hero">
      <div class="feature-hero-inner">
        <p class="section-label">Design Plans</p>
        <h1>Original Farr Design Plans</h1>
        <p class="hero-sub">Purchase and download high-resolution design drawing PDFs from our archives for your personal use &mdash; for display at home or to support maintenance and repair. Buy the full set or only the drawing you need.</p>
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
          <p>The Farr Yacht Design archive spans the full history of the studio &mdash; from early production one-designs to America&rsquo;s Cup campaigns, ocean racers, and superyachts. Original drawings are held in Annapolis. Digitization is an ongoing program; new plan sets are added regularly. All plan purchases require acceptance of a usage agreement. Plans are sold for personal use only &mdash; display, maintenance, and repair. Construction of a new boat or replacement components requires a separate licensing agreement &mdash; <a href="contact.html">contact us</a> to discuss.</p>
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
      if (status === 'scanned_available') return '<span class="plan-badge plan-badge--available">Scanned Plans</span>';
      if (status === 'request_from_shed') return '<span class="plan-badge" style="color:#d97706;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);display:inline-flex;align-items:center;font-family:var(--font-mono);font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;padding:0.25rem 0.65rem;border-radius:100px;">Archive</span>';
      if (status === 'not_digitized') return '<span class="plan-badge plan-badge--digitizing">Digitizing</span>';
      return '<span class="plan-badge" style="color:var(--text-muted);background:rgba(85,96,112,0.08);border:1px solid rgba(85,96,112,0.2);display:inline-flex;align-items:center;font-family:var(--font-mono);font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;padding:0.25rem 0.65rem;border-radius:100px;">Coming Soon</span>';
    }

    function statusLabel(status) {
      if (status === 'available') return 'Purchase Plan Set';
      if (status === 'scanned_available') return 'View Plans';
      if (status === 'request_from_shed') return 'Request This Plan';
      if (status === 'not_digitized') return 'Join Waitlist';
      return '';
    }

    function statusClass(status) {
      if (status === 'available') return 'plan-card--available';
      if (status === 'scanned_available') return 'plan-card--available';
      if (status === 'request_from_shed') return '';
      return 'plan-card--digitizing';
    }

    function renderHub() {
      var filtered = ALL_PLANS.filter(function(p) {
        if (currentFilter !== 'all') {
          if (currentFilter === 'available') {
            if (p.status !== 'available' && p.status !== 'scanned_available') return false;
          } else if (p.status !== currentFilter) return false;
        }
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
      var cAvail = ALL_PLANS.filter(function(p){return p.status==='available'||p.status==='scanned_available';}).length;
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
        var priceStr = p.price ? ' &mdash; $' + p.price : '';
        var action = '';
        if (p.status === 'available' && p.planId) {
          action = '<button class="btn-buy" style="font-size:0.78rem;padding:0.5rem 1rem;" onclick="initCheckout(\\''+escHtml(p.planId)+'\\')">Purchase'+priceStr+'</button>';
        } else if (p.status === 'available' || p.status === 'scanned_available') {
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

# 8. Generate sitemap.xml (Sprint 13)
from datetime import datetime
sitemap_urls = []
today = datetime.now().strftime('%Y-%m-%d')

# Static pages (high priority)
static_pages = [
    ('/', '1.0'),
    ('/portfolio.html', '0.9'),
    ('/design-plans.html', '0.8'),
    ('/services.html', '0.7'),
    ('/about.html', '0.7'),
    ('/racing.html', '0.6'),
    ('/contact.html', '0.6'),
    ('/team.html', '0.5'),
    ('/partners.html', '0.5'),
    ('/news.html', '0.5'),
    ('/awards.html', '0.5'),
    ('/press-kit.html', '0.4'),
    ('/kiboko-4.html', '0.6'),
    ('/volvo-ocean-race.html', '0.6'),
    ('/whitbread-heritage.html', '0.6'),
    ('/tp52-heritage.html', '0.6'),
    ('/americas-cup.html', '0.6'),
    ('/superyachts.html', '0.6'),
    ('/consulting.html', '0.6'),
    ('/farr-40.html', '0.6'),
    ('/gelliceaux.html', '0.6'),
]

for path, priority in static_pages:
    sitemap_urls.append(f'  <url>\n    <loc>{SITE_URL}{path}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>{priority}</priority>\n  </url>')

# Yacht detail pages (medium priority)
for boat in boats:
    slug = boat.get("slug", "")
    if not slug:
        continue
    year = boat.get("year")
    lastmod = f"{int(year)}-01-01" if year and int(year) >= 1964 else "2024-01-01"
    sitemap_urls.append(f'  <url>\n    <loc>{SITE_URL}/yacht/{slug}.html</loc>\n    <lastmod>{lastmod}</lastmod>\n    <priority>0.5</priority>\n  </url>')

sitemap_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(sitemap_urls)}
</urlset>
'''

with open(os.path.join(SITE, "sitemap.xml"), 'w') as f:
    f.write(sitemap_xml)
print(f"Generated sitemap.xml ({len(sitemap_urls)} URLs)")

# ─── Generate yacht_cards.json (Sprint IMG-41) ───
# Pre-resolved image data for feature pages to consume

yacht_cards = {}
for boat in boats:
    slug = boat.get("slug", "")
    if not slug:
        continue
    name = boat.get("name", "") or boat.get("title", "")
    design_num = boat.get("designNumber", "")
    year = boat.get("year", "")
    design_type = boat.get("designType", "")
    builder = boat.get("builder", "")
    specs_obj = boat.get("specs") or {}
    loa = specs_obj.get("loa", {}) if isinstance(specs_obj, dict) else {}
    loa_ft = loa.get("ft") if isinstance(loa, dict) else None

    hero = resolve_image(boat, context="hero")
    card = resolve_image(boat, context="card")

    yacht_cards[slug] = {
        "slug": slug,
        "designNumber": str(design_num),
        "name": str(name) if name else "",
        "year": year,
        "designType": design_type,
        "builder": str(builder) if builder else "",
        "loaFt": loa_ft,
        "hero": {
            "url": hero["url"],
            "hasImage": hero["has_image"],
            "cropHint": hero["crop_hint"],
            "alt": hero["alt"],
        },
        "card": {
            "url": card["url"],
            "hasImage": card["has_image"],
            "cropHint": card["crop_hint"],
            "alt": card["alt"],
        },
    }

cards_path = os.path.join(SITE, "yacht_cards.json")
with open(cards_path, 'w', encoding='utf-8') as f:
    json.dump(yacht_cards, f, ensure_ascii=False, separators=(',', ':'))
print(f"Generated yacht_cards.json ({len(yacht_cards)} designs)")

# ─── Build-time WebP conversion (Sprint IMG-44) ───
# Generates .webp for all JPG/JPEG/PNG images that don't already have a WebP sibling.
# Quality 80, max dimension 1600px.

try:
    from PIL import Image as PILImage
    WEBP_QUALITY = 80
    WEBP_MAX_DIM = 1600
    images_dir = os.path.join(SITE, "images")
    webp_created = 0
    webp_skipped = 0
    if os.path.isdir(images_dir):
        existing_files = set(os.listdir(images_dir))
        for img_file in sorted(existing_files):
            name, ext = os.path.splitext(img_file)
            if ext.lower() not in ('.jpg', '.jpeg', '.png'):
                continue
            webp_name = name + '.webp'
            if webp_name in existing_files:
                webp_skipped += 1
                continue
            src_path = os.path.join(images_dir, img_file)
            dst_path = os.path.join(images_dir, webp_name)
            try:
                with PILImage.open(src_path) as pil_img:
                    w, h = pil_img.size
                    if max(w, h) > WEBP_MAX_DIM:
                        ratio = WEBP_MAX_DIM / max(w, h)
                        pil_img = pil_img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
                    if pil_img.mode in ('RGBA', 'P'):
                        pil_img = pil_img.convert('RGB')
                    pil_img.save(dst_path, 'WEBP', quality=WEBP_QUALITY)
                    webp_created += 1
            except Exception as e:
                print(f"  WebP conversion failed for {img_file}: {e}")
    print(f"\nWebP conversion: {webp_created} created, {webp_skipped} already existed")
except ImportError:
    print("\nWebP conversion skipped (Pillow not available)")

# ─── Image Coverage Report (Sprint IMG-44) ───
# Generates image_coverage.json + image_coverage.html with gap/orphan analysis.

images_dir_cov = os.path.join(SITE, "images")
all_image_files = set()
if os.path.isdir(images_dir_cov):
    all_image_files = set(f for f in os.listdir(images_dir_cov)
                         if os.path.isfile(os.path.join(images_dir_cov, f))
                         and not f.startswith('.'))

# Collect referenced images from all visible boats
referenced_images = set()
boats_with_hero = 0
boats_without_hero = 0
boats_with_gallery = 0
gallery_total = 0
missing_heroes = []
broken_gallery_refs = []

for boat in boats:
    slug = boat.get("slug", "")
    images_obj = boat.get("images") or {}
    hero_resolved = resolve_image(boat, context="hero")

    if hero_resolved["has_image"]:
        boats_with_hero += 1
        hero_fname = hero_resolved["url"].split("/")[-1]
        referenced_images.add(hero_fname)
    else:
        boats_without_hero += 1
        missing_heroes.append({"designNumber": boat.get("designNumber", "?"),
                               "name": str(boat.get("name", "?")),
                               "slug": slug})

    gallery = images_obj.get("gallery") or []
    valid_gallery = []
    for gf in gallery:
        if gf and isinstance(gf, str):
            if gf.lower() in existing_images:
                referenced_images.add(gf)
                valid_gallery.append(gf)
            else:
                broken_gallery_refs.append({"designNumber": boat.get("designNumber", "?"),
                                            "file": gf})
    if valid_gallery:
        boats_with_gallery += 1
        gallery_total += len(valid_gallery)

# Find orphan images (exist on disk but not referenced by any boat)
orphan_images = []
for f in sorted(all_image_files):
    if f.endswith('.webp'):
        continue  # WebP files are auto-generated siblings
    if f.startswith('og-') or f.startswith('logo') or f.startswith('favicon'):
        continue  # Site-level assets
    if f not in referenced_images:
        orphan_images.append(f)

# Coverage stats
total_visible = len(boats)
hero_pct = round(100 * boats_with_hero / total_visible, 1) if total_visible else 0

from datetime import datetime
_now_iso = datetime.now().isoformat()

coverage_data = {
    "generated": _now_iso,
    "totalVisibleDesigns": total_visible,
    "heroImageCoverage": {"count": boats_with_hero, "missing": boats_without_hero,
                          "percentage": hero_pct},
    "galleryCoverage": {"designsWithGallery": boats_with_gallery,
                        "totalGalleryImages": gallery_total},
    "missingHeroes": missing_heroes[:50],
    "brokenGalleryRefs": broken_gallery_refs[:50],
    "orphanImages": orphan_images[:100],
    "totalImagesOnDisk": len(all_image_files),
    "totalReferencedImages": len(referenced_images),
}

# Write JSON
cov_json_path = os.path.join(SITE, "image_coverage.json")
with open(cov_json_path, "w") as f:
    json.dump(coverage_data, f, indent=2)

# Write HTML dashboard
cov_html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Image Coverage Report</title>
<style>body{{font-family:system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;color:#e0e0e0;background:#0d1117;}}
h1{{font-size:1.5rem;}}h2{{font-size:1.1rem;margin-top:2rem;border-bottom:1px solid #30363d;padding-bottom:0.5rem;}}
.stat{{display:inline-block;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1rem 1.5rem;margin:0.5rem;text-align:center;}}
.stat-num{{font-size:2rem;font-weight:700;color:#58a6ff;}}.stat-label{{font-size:0.8rem;color:#8b949e;}}
table{{width:100%;border-collapse:collapse;margin-top:0.5rem;}}th,td{{text-align:left;padding:0.4rem 0.75rem;border-bottom:1px solid #21262d;font-size:0.85rem;}}
th{{color:#8b949e;font-weight:600;}}tr:hover{{background:#161b22;}}
.warn{{color:#d29922;}}.ok{{color:#3fb950;}}.bad{{color:#f85149;}}
</style></head><body>
<h1>Image Coverage Report</h1>
<p style="color:#8b949e;">Generated: {_now_iso}</p>
<div>
<div class="stat"><div class="stat-num {'ok' if hero_pct > 80 else 'warn' if hero_pct > 50 else 'bad'}">{hero_pct}%</div><div class="stat-label">Hero Coverage</div></div>
<div class="stat"><div class="stat-num">{boats_with_hero}</div><div class="stat-label">With Hero</div></div>
<div class="stat"><div class="stat-num warn">{boats_without_hero}</div><div class="stat-label">Missing Hero</div></div>
<div class="stat"><div class="stat-num">{boats_with_gallery}</div><div class="stat-label">With Gallery</div></div>
<div class="stat"><div class="stat-num">{gallery_total}</div><div class="stat-label">Gallery Images</div></div>
<div class="stat"><div class="stat-num">{len(all_image_files)}</div><div class="stat-label">Files on Disk</div></div>
<div class="stat"><div class="stat-num">{len(orphan_images)}</div><div class="stat-label">Orphan Files</div></div>
</div>
'''
if missing_heroes:
    cov_html += '<h2>Missing Hero Images (top 50)</h2><table><tr><th>#</th><th>Name</th><th>Slug</th></tr>'
    for m in missing_heroes[:50]:
        cov_html += f'<tr><td>{m["designNumber"]}</td><td>{m["name"]}</td><td>{m["slug"]}</td></tr>'
    cov_html += '</table>'

if broken_gallery_refs:
    cov_html += '<h2 class="bad">Broken Gallery References</h2><table><tr><th>#</th><th>Missing File</th></tr>'
    for b in broken_gallery_refs[:50]:
        cov_html += f'<tr><td>{b["designNumber"]}</td><td class="bad">{b["file"]}</td></tr>'
    cov_html += '</table>'

if orphan_images:
    cov_html += f'<h2>Orphan Images ({len(orphan_images)} files not referenced by any design)</h2><table><tr><th>File</th></tr>'
    for o in orphan_images[:100]:
        cov_html += f'<tr><td>{o}</td></tr>'
    cov_html += '</table>'

cov_html += '</body></html>'

cov_html_path = os.path.join(SITE, "image_coverage.html")
with open(cov_html_path, "w") as f:
    f.write(cov_html)

print(f"\n{'='*50}")
print(f"IMAGE COVERAGE REPORT")
print(f"{'='*50}")
print(f"  Hero coverage: {hero_pct}% ({boats_with_hero}/{total_visible} designs)")
print(f"  Gallery: {boats_with_gallery} designs with {gallery_total} images")
print(f"  Orphan files: {len(orphan_images)} unreferenced images")

# Prominent build warnings
_img_warnings = 0
if broken_gallery_refs:
    _img_warnings += len(broken_gallery_refs)
    print(f"\n  ⚠ WARNING: {len(broken_gallery_refs)} broken gallery references:")
    for b in broken_gallery_refs[:5]:
        print(f"      #{b['designNumber']}: {b['file']}")
    if len(broken_gallery_refs) > 5:
        print(f"      ... and {len(broken_gallery_refs) - 5} more")

# Warn about featured designs missing heroes
featured_slugs = {'788', '768', '691', '442', '778', '615', '435', '591',
                  '190', '131', '378', '757', '471', '533', '541'}
featured_missing = [m for m in missing_heroes if m.get('slug') in featured_slugs]
if featured_missing:
    _img_warnings += len(featured_missing)
    print(f"\n  ⚠ WARNING: {len(featured_missing)} featured designs missing hero images:")
    for fm in featured_missing:
        print(f"      #{fm['designNumber']} ({fm['name']})")

if _img_warnings == 0:
    print(f"\n  ✓ No image warnings")
print(f"  Reports: image_coverage.json, image_coverage.html")

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

# ─── POST-BUILD QA: Semantic Link Audit ───
# Scans all static HTML pages for yacht-card links and verifies destinations.
# Catches: broken yacht links, circular self-links, wrong-destination links to
# generic pages (portfolio.html, superyachts.html) when a yacht page exists.

print(f"\n{'='*50}")
print("POST-BUILD QA: Link Audit")
print(f"{'='*50}")

# Build set of all generated yacht pages + known feature pages
yacht_pages_set = set()
for fname in os.listdir(os.path.join(SITE, "yacht")):
    if fname.endswith(".html"):
        yacht_pages_set.add(f"yacht/{fname}")

# Known feature pages that are valid link targets
feature_pages = {"kiboko-4.html", "gelliceaux.html", "americas-cup.html",
                 "whitbread-heritage.html", "volvo-ocean-race.html"}

# All valid slug set from boats.json
valid_slugs = {b['slug'] for b in all_boats}

# Scan static HTML files for yacht-card links
_card_link_re = re.compile(r'<a\s+href="([^"]+)"\s+class="yacht-card[^"]*"', re.IGNORECASE)
_any_yacht_link_re = re.compile(r'href="(yacht/[^"]+\.html)"')
_self_link_re = re.compile(r'class="yacht-card[^"]*"')

qa_errors = []
qa_warnings = []
static_htmls = [f for f in os.listdir(SITE) if f.endswith('.html')
                and f not in ('portfolio.html',)]  # portfolio is generated, skip

for html_file in sorted(static_htmls):
    filepath = os.path.join(SITE, html_file)
    with open(filepath, 'r', encoding='utf-8') as fh:
        content = fh.read()

    # Find all yacht-card links
    for m in _card_link_re.finditer(content):
        href = m.group(1)
        line_num = content[:m.start()].count('\n') + 1

        # Check for circular self-links
        if href == html_file:
            qa_errors.append(f"  CIRCULAR: {html_file}:{line_num} → {href}")
            continue

        # Check yacht/ links point to existing pages
        if href.startswith("yacht/"):
            if href not in yacht_pages_set:
                qa_errors.append(f"  BROKEN: {html_file}:{line_num} → {href} (page not found)")
            continue

        # Check for yacht-card links to generic pages (likely wrong destination)
        if href in ("portfolio.html", "superyachts.html", "racing.html", "partners.html"):
            # Extract design number from nearby content
            context = content[m.start():m.start()+500]
            dn_match = re.search(r'yacht-card-number[^>]*>#?(\d+)', context)
            if dn_match:
                dn = dn_match.group(1)
                expected = f"yacht/{dn}.html"
                if expected in yacht_pages_set:
                    qa_errors.append(f"  WRONG DEST: {html_file}:{line_num} → {href} "
                                     f"(card #{dn} should link to {expected})")
                else:
                    qa_warnings.append(f"  NO YACHT PAGE: {html_file}:{line_num} → {href} "
                                       f"(card #{dn} has no yacht page)")

    # Check all yacht/ hrefs (not just yacht-card links)
    for m in _any_yacht_link_re.finditer(content):
        href = m.group(1)
        if href not in yacht_pages_set:
            line_num = content[:m.start()].count('\n') + 1
            qa_errors.append(f"  BROKEN: {html_file}:{line_num} → {href} (page not found)")

if qa_errors:
    print(f"\n  ERRORS ({len(qa_errors)}):")
    for e in qa_errors:
        print(e)
if qa_warnings:
    print(f"\n  WARNINGS ({len(qa_warnings)}):")
    for w in qa_warnings:
        print(w)
if not qa_errors and not qa_warnings:
    print("  All links verified. 0 errors, 0 warnings.")
else:
    print(f"\n  Summary: {len(qa_errors)} errors, {len(qa_warnings)} warnings")
    if qa_errors:
        print("  *** FIX ERRORS BEFORE DEPLOYING ***")
