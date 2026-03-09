# Archive Parity Review Spreadsheet

## Overview

The **FarrDesigns_Parity_Review.xlsx** spreadsheet provides a comprehensive comparison of the legacy Farr Yacht Design website (524 pages) with the new website (415 pages). It classifies every legacy design page and determines the appropriate migration strategy.

## File Location

```
/sessions/trusting-elegant-johnson/mnt/web/NewFYDWebSite/www/archive/FarrDesigns_Parity_Review.xlsx
```

## Columns Explained

| Column | Description |
|--------|-------------|
| **Legacy Page** | Filename from the old site (e.g., `100.html`, `028results.html`) |
| **Design Number** | Extracted design number from filename or content (e.g., `100` from `100.html`) |
| **Boat Name** | Boat name extracted from the HTML title tag (e.g., "Farr 44", "NOELEX 30") |
| **New Site Page** | Path to matching page in the new site (e.g., `/100.html`, `/yacht/kiboko-4.html`) |
| **New Site Status** | Classification of the new site page: "Modern page", "Legacy stub", or "Not migrated" |
| **Decision** | Auto-generated recommendation (color-coded): |
| **Notes** | Additional context or specific action needed |

## Decision Categories

### Keep (modern) — Green ✓
**33 pages (11.4%)**

- Matching new site page exists and contains real, modern content
- These pages are in good shape and ready for production
- Action: Review for completeness and SEO optimization

### Redirect — Yellow →
**218 pages (75.2%)**

- Legacy stub exists in new site (same filename as old page)
- Corresponds to a modern yacht/ page with real content
- Action: Set up permanent redirects from old numbered pages to new yacht pages
- Example: `100.html` → `/yacht/farr-44.html`

### Defer — Gray ⏸
**0 pages (0%)**

- Legacy content exists but no modern equivalent yet
- Requires future work or review
- Action: Evaluate whether to create modern page, retire, or repurpose content
- (Note: The current migration handles most pages, so this category is empty)

### Retire — Red ✗
**39 pages (13.4%)**

- Pages that should be discontinued in the migration
- Mostly results pages (`*results.html`) and photo galleries (`*photos.html`)
- Action: Remove from new site, implement HTTP 410 Gone responses
- These served historical/archival purposes but are outdated

## How to Use This Spreadsheet

### For Migration Team

1. **Sort by Decision** to group pages by action type
2. **Filter by "Redirect"** to identify which legacy pages need URL redirects
3. **Review "Keep (modern)"** pages for completeness
4. **Plan "Retire"** pages — ensure no incoming links before removing

### For SEO

1. Check "Boat Name" column to identify key vessels
2. Verify that "Keep (modern)" pages have proper meta descriptions
3. Plan 301 redirects for "Redirect" pages to maintain link equity

### For QA Testing

1. Sample pages from each decision category
2. Verify "Keep (modern)" pages display correctly
3. Test that redirects are properly configured
4. Confirm "Retire" pages return appropriate HTTP status codes

## Formatting Features

- **Bold header row** with blue background for easy identification
- **Auto-fitted column widths** for readable content
- **Color coding** in Decision column for quick visual scanning
- **Frozen top row** — scroll down while keeping headers visible
- **Summary statistics** at bottom showing counts by decision

## Regenerating the Spreadsheet

To regenerate the spreadsheet after changes:

```bash
cd /sessions/trusting-elegant-johnson/mnt/web/NewFYDWebSite/www/archive
python3 generate_parity_review.py
```

The script will:
1. Scan the legacy site directory
2. Scan the new site directory
3. Extract titles from HTML files
4. Match legacy pages to new site equivalents
5. Classify each page automatically
6. Generate a new spreadsheet with summary statistics

## Key Findings

| Metric | Count |
|--------|-------|
| Legacy pages analyzed | 290 |
| Pages with modern equivalents | 218 (75.2%) |
| Pages needing new implementation | 33 (11.4%) |
| Pages to retire | 39 (13.4%) |

## Technical Details

### Detection Logic

**Modern Pages vs. Legacy Stubs:**
- Modern pages have current navigation structure with links like `../portfolio.html`, `nav-logo` class
- Legacy stubs retain Adobe Muse markers (`museutils.js`, `museconfig.js`, CSS with `crc=` values)

**Design Number Extraction:**
- Pattern: `^\d+` from filename (e.g., `100.html` → `100`, `121m.html` → `121`)

**Boat Name Extraction:**
- Modern format: Text before "—" in title tag (e.g., "10' General Purpose Dinghy")
- Legacy format: Text between "|" and "(Design" in title tag (e.g., "Farr 44")

**Page Matching:**
- Primary: Exact filename match in new site root
- Secondary: Design number match in yacht/ subdirectory titles
- Fallback: "Not migrated" if no match found

## Next Steps

1. **Redirect Configuration** — Set up 301 redirects for 218 "Redirect" pages
2. **Content Review** — Verify 33 "Keep (modern)" pages are production-ready
3. **Retirement Planning** — Archive or remove 39 "Retire" pages with proper HTTP responses
4. **Testing** — Run full QA on sample pages from each category
5. **Monitoring** — Track 404 errors after launch to catch missed pages

---

**Generated:** March 9, 2026
**Script Location:** `/sessions/trusting-elegant-johnson/mnt/web/NewFYDWebSite/www/archive/generate_parity_review.py`
