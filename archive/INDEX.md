# Farr Yacht Design - Archive Parity Review

## Overview

This directory contains the archive parity review analysis comparing the legacy Farr Yacht Design website with the new site, created to guide the migration strategy.

## Files in This Directory

### 1. **FarrDesigns_Parity_Review.xlsx**
The main deliverable - a professional Excel spreadsheet analyzing all 290 legacy design pages.

**Contents:**
- 290 legacy design pages (rows 2-291)
- 7 analytical columns: Legacy Page, Design Number, Boat Name, New Site Page, New Site Status, Decision, Notes
- Color-coded decisions (green/yellow/red)
- Summary statistics section
- Formatted with frozen header row and auto-fitted columns

**How to Use:**
1. Open in Microsoft Excel, Google Sheets, or compatible spreadsheet application
2. Sort by "Decision" column to group similar action items
3. Filter by decision type to see specific pages that need attention
4. Review boat names and design numbers for content verification

**Decision Categories:**
- **Keep (modern)** [GREEN] - 33 pages: Modern pages with real content, ready to use
- **Redirect** [YELLOW] - 218 pages: Legacy stubs that need 301 redirects to modern pages
- **Retire** [RED] - 39 pages: Pages to discontinue (results pages, photo galleries, etc.)

### 2. **generate_parity_review.py**
Python 3 script that generates/regenerates the spreadsheet.

**Features:**
- Scans both legacy and new site directories
- Extracts page titles from HTML `<title>` tags
- Automatically classifies pages as modern or legacy
- Generates professional Excel formatting
- Produces summary statistics

**Usage:**
```bash
cd /sessions/trusting-elegant-johnson/mnt/web/NewFYDWebSite/www/archive
python3 generate_parity_review.py
```

**Requirements:**
- Python 3.6+
- openpyxl library (`pip install openpyxl`)

### 3. **PARITY_REVIEW_README.md**
Comprehensive documentation explaining:
- What each column means
- How to interpret decision categories
- Technical details on page detection logic
- Next steps and action items
- How to regenerate the spreadsheet

## Quick Statistics

| Metric | Value |
|--------|-------|
| Total Legacy Pages | 290 |
| Pages Ready (Keep) | 33 (11.4%) |
| Pages Needing Redirects | 218 (75.2%) |
| Pages to Retire | 39 (13.4%) |
| Old Site Size | 524 pages |
| New Site Size | 415 pages |

## Analysis Methodology

### Page Classification

**Modern Page Detection:**
- Looks for modern navigation structure (`nav-logo` class, relative paths to `../portfolio.html`)
- Identifies pages with real, current content
- Typically found in `/yacht/` subdirectory

**Legacy Stub Detection:**
- Identifies Adobe Muse markers (`museutils.js`, `museconfig.js`)
- Finds CSS files with `crc=` values (Muse build pattern)
- Detects old navigation structure

**Results & Gallery Pages:**
- Identified by filename patterns (`*results.html`, `*photos.html`, `*gallery.html`)
- Marked for retirement as archival/historical content

### Design Number Extraction
Pattern: `^\d+` from filename
- Examples: `100.html` → `100`, `121m.html` → `121`, `028results.html` → `028`

### Boat Name Extraction
- Modern format: Text before "—" in title (e.g., "10' General Purpose Dinghy")
- Legacy format: Text between "|" and "(Design" in title (e.g., "Farr 44")

## Recommendations

### Immediate Actions

1. **Set up 301 Redirects** (218 pages)
   - Map legacy numbered pages to new yacht/ pages
   - Example: `/100.html` → `/yacht/farr-44.html`
   - Use .htaccess, web.config, or application router

2. **Review Modern Pages** (33 pages)
   - Verify content completeness
   - Check SEO metadata (titles, descriptions)
   - Test functionality and forms

3. **Plan Retirement** (39 pages)
   - Archive content if needed
   - Implement HTTP 410 Gone responses
   - Ensure no external links point to these pages

### Testing Strategy

1. **Sample Testing** - Test pages from each category:
   - 5-10 "Keep (modern)" pages
   - 10-20 "Redirect" pages
   - 5-10 "Retire" pages

2. **Redirect Verification**
   - Verify 301 status codes
   - Check that destination pages load correctly
   - Ensure no redirect chains

3. **Link Analysis**
   - Check for broken internal links
   - Verify all yacht page links are correct
   - Test navigation from portfolio page

### Post-Launch Monitoring

1. Set up 404 error alerts in analytics
2. Monitor redirect success rates
3. Identify any missed pages or incorrect mappings
4. Track which legacy URLs still receive traffic

## Technical Notes

### Data Integrity

All analysis is read-only - no HTML files were modified during this analysis. The script only reads from:
- `/sessions/trusting-elegant-johnson/mnt/web/OldFYDWebSite/wwwroot/wwwroot/` (legacy)
- `/sessions/trusting-elegant-johnson/mnt/web/NewFYDWebSite/www/` (new)

### File Size Analysis

- Numbered pages in new site root (100.html, 128.html, etc.) are typically 200KB+
- Modern yacht/ pages are typically 30-50KB
- Size difference is due to legacy pages retaining old assets and stylesheets

## Support

For questions about the analysis or spreadsheet:
1. Review PARITY_REVIEW_README.md for detailed explanations
2. Check the "Notes" column in the spreadsheet for page-specific context
3. Re-run generate_parity_review.py after changes to site structure

---

**Generated:** March 9, 2026  
**Legacy Site Analyzed:** 290 HTML design pages  
**Status:** Complete and ready for migration planning
