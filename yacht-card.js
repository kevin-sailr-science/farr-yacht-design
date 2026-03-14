/**
 * Data-driven yacht card renderer.
 * Fetches yacht_cards.json and populates all elements with data-yacht-card attribute.
 *
 * Usage in HTML:
 *   <a data-yacht-card="691" class="yacht-card" style="text-decoration:none;"></a>
 *
 * Optional attributes:
 *   data-card-height="200"      — image height in px (default: 160)
 *   data-card-label="Custom"    — override display name
 *   data-card-meta="Custom meta"— override meta line
 *   data-card-featured          — adds yacht-card--featured class
 *   data-card-badge="Badge"     — shows badge overlay on image
 *   data-card-badge-class="cls" — custom badge CSS class (e.g. "result-badge result-badge--winner")
 *   data-card-desc="Text"       — optional description paragraph below meta
 *
 * Sprint IMG-43 — Farr Yacht Design
 */
(function() {
  'use strict';

  // Self-contained WebP detection (replaces Sprint 39 dependency)
  var _supportsWebp = (function() {
    try { var c = document.createElement('canvas'); c.width = c.height = 1;
      return c.toDataURL('image/webp').indexOf('data:image/webp') === 0; }
    catch(e) { return false; }
  })();

  var CARDS_URL = '/yacht_cards.json';
  var _cache = null;

  function loadCards(cb) {
    if (_cache) return cb(_cache);
    var xhr = new XMLHttpRequest();
    xhr.open('GET', CARDS_URL);
    xhr.onload = function() {
      if (xhr.status === 200) {
        _cache = JSON.parse(xhr.responseText);
        cb(_cache);
      }
    };
    xhr.send();
  }

  function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function renderCard(el, cards) {
    var slug = el.getAttribute('data-yacht-card');
    var card = cards[slug];
    if (!card) {
      console.warn('yacht-card: no data for slug "' + slug + '"');
      return;
    }

    var height = el.getAttribute('data-card-height') || '160';
    var label = el.getAttribute('data-card-label') || card.name || '';
    var meta = el.getAttribute('data-card-meta');
    var featured = el.hasAttribute('data-card-featured');
    var badge = el.getAttribute('data-card-badge') || '';
    var badgeClass = el.getAttribute('data-card-badge-class') || '';
    var desc = el.getAttribute('data-card-desc') || '';

    // Build meta line if not overridden
    if (!meta) {
      var parts = [];
      if (card.loaFt) parts.push(card.loaFt + "'");
      if (card.designType) parts.push(card.designType);
      if (card.year) parts.push(card.year);
      meta = parts.join(' | ');
    }

    // Image
    var imgData = card.card || card.hero;
    var imgUrl = imgData.url;
    var hasImg = imgData.hasImage;
    var cropHint = imgData.cropHint;

    // Use WebP if available
    if (hasImg && _supportsWebp && imgUrl.match(/\.(jpg|jpeg|png)$/i)) {
      imgUrl = imgUrl.replace(/\.(jpg|jpeg|png)$/i, '.webp');
    }

    var imgStyle = '';
    if (hasImg) {
      imgStyle = "background-image:url('" + imgUrl + "');";
      if (cropHint) imgStyle += 'background-position:' + cropHint + ';';
    }
    imgStyle += 'height:' + height + 'px;';
    if (featured) imgStyle += 'position:relative;';

    // Set href if not already set
    if (!el.getAttribute('href')) {
      el.setAttribute('href', 'yacht/' + slug + '.html');
    }

    // Add featured class
    if (featured && el.className.indexOf('yacht-card--featured') === -1) {
      el.className += ' yacht-card--featured';
    }

    // Build inner HTML
    var html = '<div class="yacht-card-image" style="' + imgStyle + '"';
    if (hasImg) {
      html += ' role="img" aria-label="' + escHtml(imgData.alt || label) + '"';
    }
    html += '>';

    if (!hasImg) {
      html += '<span class="img-tbc"><svg class="img-tbc-icon" viewBox="0 0 100 60" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 45 Q20 42 30 44 Q50 35 70 40 Q80 38 90 42 L90 50 Q80 48 70 49 Q50 47 30 50 Q20 49 10 50 Z" fill="currentColor" opacity="0.15"/><path d="M50 10 L50 38 M50 10 L75 30 Q65 28 55 32 Z" stroke="currentColor" stroke-width="1" fill="currentColor" opacity="0.12"/></svg><span class="img-tbc-label">Photo coming soon</span></span>';
    }

    if (badge) {
      if (badgeClass) {
        html += '<span class="' + escHtml(badgeClass) + '" style="position:absolute;top:0.75rem;left:0.75rem;">' + escHtml(badge) + '</span>';
      } else {
        html += '<span style="position:absolute;top:8px;right:8px;background:var(--accent,#2a5c8a);color:#fff;font-size:0.7rem;padding:2px 8px;border-radius:3px;">' + escHtml(badge) + '</span>';
      }
    }

    html += '</div>';
    html += '<div class="yacht-card-body">';
    html += '<div class="yacht-card-number">' + escHtml(card.designNumber ? '#' + card.designNumber : '') + '</div>';
    html += '<div class="yacht-card-name">' + escHtml(label) + '</div>';
    html += '<div class="yacht-card-meta">' + escHtml(meta) + '</div>';
    if (desc) {
      html += '<p style="font-size:0.82rem;color:var(--text-secondary);margin-top:0.5rem;">' + escHtml(desc) + '</p>';
    }
    html += '</div>';

    el.innerHTML = html;
  }

  function init() {
    var els = document.querySelectorAll('[data-yacht-card]');
    if (!els.length) return;
    loadCards(function(cards) {
      for (var i = 0; i < els.length; i++) {
        renderCard(els[i], cards);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
