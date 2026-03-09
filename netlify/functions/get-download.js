/**
 * get-download.js
 * Netlify Function - Secure Download Token Validator
 *
 * GET /.netlify/functions/get-download?token={TOKEN}
 * GET /.netlify/functions/get-download?session_id={CHECKOUT_SESSION_ID}
 *
 * Called from two contexts:
 *   1. purchase-success.html - validates session_id, returns order details + download URL
 *   2. Direct download link from email - validates HMAC token, redirects to file
 *
 * Mock sessions (session_id starting with "mock_session_") are handled without Stripe.
 *
 * Required environment variables:
 *   STRIPE_SECRET_KEY      - to look up real session details
 *   DOWNLOAD_HMAC_SECRET   - matches secret used in stripe-webhook.js
 *   DOWNLOAD_BASE_URL      - where PDFs are stored (e.g. https://plans.farrdesign.com)
 */

const crypto = require('crypto');

const PLAN_FILES = {
  'farr-40-full': 'farr-40-full-plans.pdf',
  'farr-1020-full': 'farr-1020-plans.pdf',
  'farr-1120-full': 'farr-1120-plans.pdf',
  'farr-740-sport-full': 'farr-740-sport-plans.pdf',
  'noelex-30-full': 'noelex-30-plans.pdf',
  'farr-92-full': 'farr-92-plans.pdf',
  'farr-920-full': 'farr-920-plans.pdf',
  'farr-11s-full': 'farr-11s-plans.pdf',
  'beneteau-first-407-full': 'beneteau-first-407-plans.pdf',
  'farr-63-kiwi-spirit-full': 'farr-63-kiwi-spirit-plans.pdf',
};

const PLAN_NAMES = {
  'farr-40-full': 'Farr 40 One-Design — Full Plan Set',
  'farr-1020-full': 'Farr 1020 — Full Plan Set',
  'farr-1120-full': 'Farr 1120 — Plan Set',
  'farr-740-sport-full': 'Farr 740 Sport — Plan Set',
  'noelex-30-full': 'Noelex 30 — Full Plan Set',
  'farr-92-full': 'Farr 9.2 — Full Plan Set',
  'farr-920-full': 'Farr 920 — Full Plan Set',
  'farr-11s-full': 'Farr 11S — Full Plan Set',
  'beneteau-first-407-full': 'Beneteau First 40.7 — Plan Set',
  'farr-63-kiwi-spirit-full': 'Farr 63 "Kiwi Spirit" — Plan Set',
};

function verifyDownloadToken(token) {
  const secret = process.env.DOWNLOAD_HMAC_SECRET;
  if (!secret) throw new Error('DOWNLOAD_HMAC_SECRET not configured');

  let decoded;
  try {
    decoded = Buffer.from(token, 'base64url').toString('utf8');
  } catch (e) {
    return { valid: false, reason: 'Token decode failed' };
  }

  const lastColon = decoded.lastIndexOf(':');
  if (lastColon === -1) return { valid: false, reason: 'Malformed token' };

  const providedHmac = decoded.slice(lastColon + 1);
  const payload = decoded.slice(0, lastColon);
  const parts = payload.split(':');

  if (parts.length < 3) return { valid: false, reason: 'Malformed payload' };

  const [planId, sessionId, expiresAtStr] = parts;
  const expiresAt = parseInt(expiresAtStr, 10);

  if (Date.now() > expiresAt) {
    return { valid: false, reason: 'Download link has expired. Please contact plans@farrdesign.com to request a new link.' };
  }

  const expectedHmac = crypto.createHmac('sha256', secret).update(payload).digest('hex');
  const providedBuf = Buffer.from(providedHmac, 'hex');
  const expectedBuf = Buffer.from(expectedHmac, 'hex');

  if (providedBuf.length !== expectedBuf.length ||
      !crypto.timingSafeEqual(providedBuf, expectedBuf)) {
    return { valid: false, reason: 'Invalid download token' };
  }

  return { valid: true, planId, sessionId, expiresAt };
}

exports.handler = async function (event) {
  const params = event.queryStringParameters || {};

  /* ---- Mode 1: session_id lookup ---- */
  if (params.session_id) {
    const sessionId = params.session_id;

    /* ---- MOCK MODE: session_id starts with "mock_session_" ---- */
    if (sessionId.startsWith('mock_session_')) {
      /* Extract planId from mock session: mock_session_{timestamp}_{plan_id_underscored} */
      const parts = sessionId.split('_');
      /* parts: ['mock', 'session', timestamp, ...planIdParts] */
      const planIdUnderscored = parts.slice(3).join('_');
      const planId = planIdUnderscored.replace(/_/g, '-');
      const planName = PLAN_NAMES[planId] || 'Farr Design Plan Set';
      const siteUrl = process.env.SITE_URL || 'https://farrdesign.com';
      const mockDownloadUrl = siteUrl + '/design-plans.html?mock_download=1';
      const expiresAt = Date.now() + 48 * 60 * 60 * 1000;

      return {
        statusCode: 200,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({
          planName: planName,
          orderId: sessionId,
          amountPaid: '350.00',
          downloadUrl: mockDownloadUrl,
          expiresAt: new Date(expiresAt).toUTCString().replace('GMT', 'UTC'),
          mock: true
        })
      };
    }
    /* ---- END MOCK MODE ---- */

    const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
    let session;
    try {
      session = await stripe.checkout.sessions.retrieve(sessionId, {
        expand: ['payment_intent']
      });
    } catch (err) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({ error: 'Could not retrieve session: ' + err.message })
      };
    }

    if (session.payment_status !== 'paid') {
      return {
        statusCode: 402,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({ error: 'Payment not completed for this session.' })
      };
    }

    const planId = session.metadata && session.metadata.planId;
    const planName = (session.metadata && session.metadata.planName) || PLAN_NAMES[planId] || 'Design Plan Set';
    const amountPaid = session.amount_total ? (session.amount_total / 100).toFixed(2) : '350.00';

    if (planId && PLAN_FILES[planId]) {
      const secret = process.env.DOWNLOAD_HMAC_SECRET;
      if (secret) {
        const expiresAt = Date.now() + 48 * 60 * 60 * 1000;
        const payload = planId + ':' + sessionId + ':' + expiresAt;
        const hmac = crypto.createHmac('sha256', secret).update(payload).digest('hex');
        const token = Buffer.from(payload + ':' + hmac).toString('base64url');
        const siteUrl = process.env.SITE_URL || 'https://farrdesign.com';
        const downloadUrl = siteUrl + '/.netlify/functions/get-download?token=' + token;

        return {
          statusCode: 200,
          headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
          body: JSON.stringify({
            planName: planName,
            orderId: session.payment_intent ? session.payment_intent.id : sessionId,
            amountPaid: amountPaid,
            downloadUrl: downloadUrl,
            expiresAt: new Date(expiresAt).toUTCString().replace('GMT', 'UTC')
          })
        };
      }
    }

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({
        planName: planName,
        orderId: sessionId,
        amountPaid: amountPaid,
        downloadUrl: null
      })
    };
  }

  /* ---- Mode 2: HMAC token validation + file redirect ---- */
  if (params.token) {
    let result;
    try {
      result = verifyDownloadToken(params.token);
    } catch (err) {
      return { statusCode: 500, body: 'Server configuration error.' };
    }

    if (!result.valid) {
      return { statusCode: 403, body: result.reason || 'Invalid or expired download link.' };
    }

    const filename = PLAN_FILES[result.planId];
    if (!filename) {
      return { statusCode: 404, body: 'Plan file not found.' };
    }

    const baseUrl = process.env.DOWNLOAD_BASE_URL;
    if (!baseUrl) {
      return { statusCode: 500, body: 'Download storage not configured. Please contact plans@farrdesign.com.' };
    }

    const fileUrl = baseUrl.replace(/\/$/, '') + '/' + filename;
    return { statusCode: 302, headers: { 'Location': fileUrl }, body: '' };
  }

  return {
    statusCode: 400,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ error: 'Missing token or session_id parameter' })
  };
};
