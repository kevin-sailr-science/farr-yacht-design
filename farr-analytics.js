/**
 * Farr Yacht Design — Analytics & Event Tracking
 * GA4 custom events for Sprint 5 launch tracking
 *
 * Events tracked:
 *   contact_form_submit  — Contact page form submission
 *   waitlist_submit      — Design plans waitlist form submission
 *   checkout_start       — "Buy" button clicked on design plans
 *   plan_download        — Download link clicked on purchase-success
 *   nav_click            — Main navigation link clicked
 *   cta_click            — CTA button clicked (hero, footer band)
 *   press_kit_download   — Press kit PDF download
 */

(function() {
  'use strict';

  // Helper: send GA4 event (safe if gtag not loaded)
  function sendEvent(eventName, params) {
    if (typeof gtag === 'function') {
      gtag('event', eventName, params || {});
    }
    // Console log in dev for debugging
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      console.log('[FYD Analytics]', eventName, params || {});
    }
  }

  // Wait for DOM ready
  function onReady(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  onReady(function() {

    // --- Nav clicks ---
    document.querySelectorAll('nav a, .nav-mobile a, .footer-grid a').forEach(function(link) {
      link.addEventListener('click', function() {
        sendEvent('nav_click', {
          link_text: this.textContent.trim(),
          link_url: this.getAttribute('href')
        });
      });
    });

    // --- CTA clicks (hero buttons, footer CTA band) ---
    document.querySelectorAll('.hero-cta, .hero-secondary').forEach(function(btn) {
      btn.addEventListener('click', function() {
        sendEvent('cta_click', {
          cta_text: this.textContent.trim(),
          cta_location: this.closest('.cta-band') ? 'footer_band' : 'hero'
        });
      });
    });

    // --- Contact form submit ---
    var contactForm = document.querySelector('form[name="contact"]');
    if (contactForm) {
      contactForm.addEventListener('submit', function() {
        sendEvent('contact_form_submit', {
          page: window.location.pathname
        });
      });
    }

    // --- Waitlist form submit (design plans page) ---
    var waitlistForm = document.getElementById('waitlist-form');
    if (waitlistForm) {
      waitlistForm.addEventListener('submit', function() {
        var designField = waitlistForm.querySelector('[name="design"]');
        sendEvent('waitlist_submit', {
          design_requested: designField ? designField.value : ''
        });
      });
    }

    // --- Checkout start (Buy buttons on design plans) ---
    // Hooks into the global initCheckout function if present
    if (typeof window.initCheckout === 'function') {
      var originalCheckout = window.initCheckout;
      window.initCheckout = function(planId) {
        sendEvent('checkout_start', { plan_id: planId });
        return originalCheckout.apply(this, arguments);
      };
    }
    // Also catch any btn-buy clicks as fallback
    document.querySelectorAll('.btn-buy').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var planId = this.getAttribute('data-plan-id') || 'unknown';
        sendEvent('checkout_start', { plan_id: planId });
      });
    });

    // --- Plan download (purchase-success page) ---
    document.querySelectorAll('a[href*="get-download"], a[href*="/download"]').forEach(function(link) {
      link.addEventListener('click', function() {
        sendEvent('plan_download', {
          download_url: this.getAttribute('href')
        });
      });
    });

    // --- Press kit / archive PDF downloads ---
    document.querySelectorAll('a[href$=".pdf"]').forEach(function(link) {
      link.addEventListener('click', function() {
        var href = this.getAttribute('href') || '';
        sendEvent('press_kit_download', {
          file: href.split('/').pop(),
          page: window.location.pathname
        });
      });
    });

  });
})();
