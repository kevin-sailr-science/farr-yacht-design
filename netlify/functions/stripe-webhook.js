/**
 * stripe-webhook.js
 * Netlify Function - Stripe Webhook Handler
 *
 * POST /.netlify/functions/stripe-webhook
 * Called by Stripe when payment events occur.
 * Handles: checkout.session.completed
 *
 * Required environment variables (Netlify Dashboard -> Site Config -> Env Vars):
 *   STRIPE_SECRET_KEY     - sk_live_... or sk_test_...
 *   STRIPE_WEBHOOK_SECRET - whsec_... (from Stripe Dashboard -> Webhooks)
 *   DOWNLOAD_HMAC_SECRET  - openssl rand -hex 32
 *   DOWNLOAD_BASE_URL     - https://plans.farrdesign.com (no trailing slash)
 *   SITE_URL              - https://farrdesign.com (no trailing slash)
 *   RESEND_API_KEY        - re_... (from resend.com dashboard)
 *   FROM_EMAIL            - plans@farrdesign.com (must be verified in Resend)
 */

const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
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

function generateDownloadToken(planId, sessionId) {
  const secret = process.env.DOWNLOAD_HMAC_SECRET;
  if (!secret) throw new Error('DOWNLOAD_HMAC_SECRET not configured');
  const expiresAt = Date.now() + 48 * 60 * 60 * 1000;
  const payload = planId + ':' + sessionId + ':' + expiresAt;
  const hmac = crypto.createHmac('sha256', secret).update(payload).digest('hex');
  const token = Buffer.from(payload + ':' + hmac).toString('base64url');
  return { token, expiresAt };
}

function formatExpiry(expiresAt) {
  return new Date(expiresAt).toUTCString().replace('GMT', 'UTC');
}

async function sendDownloadEmail(customerEmail, planName, downloadUrl, expiresAt) {
  const resendApiKey = process.env.RESEND_API_KEY;
  const fromEmail = process.env.FROM_EMAIL || 'plans@farrdesign.com';

  if (!resendApiKey) {
    console.warn('RESEND_API_KEY not set - skipping email to ' + customerEmail);
    console.log('Download URL (would have been emailed):', downloadUrl);
    return { success: false, reason: 'RESEND_API_KEY not configured' };
  }

  const expiryStr = formatExpiry(expiresAt);

  const html = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"></head><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f5f5f0;margin:0;padding:32px 16px;">' +
    '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;">' +
    '<tr><td style="background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1);">' +
    '<table width="100%" cellpadding="0" cellspacing="0"><tr>' +
    '<td style="background:#0a192f;padding:24px 32px;border-radius:8px 8px 0 0;">' +
    '<span style="font-family:Georgia,serif;font-size:18px;color:#fff;">Farr <span style="color:#4a9eff;">Yacht Design</span></span>' +
    '</td></tr></table>' +
    '<table width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:32px;">' +
    '<h1 style="font-family:Georgia,serif;font-size:22px;color:#0a192f;margin:0 0 8px;">Your design plans are ready</h1>' +
    '<p style="color:#475569;font-size:15px;line-height:1.5;margin:0 0 24px;">Thank you for purchasing <strong>' + planName + '</strong>. Your download link is below.</p>' +
    '<table cellpadding="0" cellspacing="0" style="margin-bottom:24px;"><tr>' +
    '<td style="background:#0a192f;border-radius:6px;padding:14px 28px;">' +
    '<a href="' + downloadUrl + '" style="color:#fff;text-decoration:none;font-size:15px;font-weight:600;">Download Plans &rarr;</a>' +
    '</td></tr></table>' +
    '<p style="color:#64748b;font-size:13px;margin:0 0 6px;">Or copy this link:</p>' +
    '<p style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;padding:10px 12px;font-size:12px;word-break:break-all;color:#334155;margin:0 0 24px;">' + downloadUrl + '</p>' +
    '<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">' +
    '<p style="color:#94a3b8;font-size:12px;line-height:1.6;margin:0;">' +
    'Link expires: <strong>' + expiryStr + '</strong><br>' +
    'If your link expires, reply to this email for a fresh one.<br>' +
    'Questions? <a href="mailto:info@farrdesign.com" style="color:#0a192f;">info@farrdesign.com</a>' +
    '</p></td></tr></table>' +
    '<table width="100%" cellpadding="0" cellspacing="0"><tr>' +
    '<td style="background:#f8fafc;padding:16px 32px;border-top:1px solid #e2e8f0;border-radius:0 0 8px 8px;">' +
    '<p style="color:#94a3b8;font-size:11px;margin:0;">Farr Yacht Design &middot; Annapolis, MD &middot; farrdesign.com</p>' +
    '</td></tr></table>' +
    '</td></tr></table></body></html>';

  const text = 'Your Farr Yacht Design plans are ready.\n\n' +
    'Purchase: ' + planName + '\n\n' +
    'Download: ' + downloadUrl + '\n\n' +
    'Expires: ' + expiryStr + '\n\n' +
    'If your link expires, reply for a fresh one.\n' +
    'Questions? info@farrdesign.com\n\n' +
    'Farr Yacht Design - Annapolis, MD';

  try {
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + resendApiKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'Farr Yacht Design <' + fromEmail + '>',
        to: [customerEmail],
        subject: 'Your design plans: ' + planName,
        html: html,
        text: text
      })
    });

    const result = await response.json();
    if (!response.ok) {
      console.error('Resend error ' + response.status + ':', JSON.stringify(result));
      return { success: false, status: response.status, error: result };
    }
    console.log('Email sent id=' + result.id + ' to=' + customerEmail);
    return { success: true, messageId: result.id };

  } catch (err) {
    console.error('Resend fetch error:', err.message);
    return { success: false, error: err.message };
  }
}

exports.handler = async function (event) {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  const sig = event.headers['stripe-signature'];
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  let stripeEvent;

  try {
    stripeEvent = stripe.webhooks.constructEvent(event.body, sig, webhookSecret);
  } catch (err) {
    console.error('Signature verification failed:', err.message);
    return { statusCode: 400, body: 'Webhook signature invalid' };
  }

  if (stripeEvent.type === 'checkout.session.completed') {
    const session = stripeEvent.data.object;
    const planId = session.metadata && session.metadata.planId;
    const customerEmail = session.customer_details && session.customer_details.email;

    if (!planId) {
      console.error('No planId in metadata, session:', session.id);
      return { statusCode: 200, body: 'OK (no planId)' };
    }

    if (session.payment_status !== 'paid') {
      return { statusCode: 200, body: 'OK (not paid yet)' };
    }

    let token, expiresAt;
    try {
      ({ token, expiresAt } = generateDownloadToken(planId, session.id));
    } catch (err) {
      console.error('Token generation failed:', err.message);
      return { statusCode: 500, body: 'Token generation failed' };
    }

    const siteUrl = process.env.SITE_URL || 'https://farrdesign.com';
    const downloadUrl = siteUrl + '/.netlify/functions/get-download?token=' + token;
    const planName = session.metadata.planName || planId;

    /* Fulfillment log (Netlify Dashboard -> Functions -> stripe-webhook -> Logs) */
    console.log('FULFILLMENT', JSON.stringify({
      sessionId: session.id,
      planId, planName,
      customerEmail: customerEmail || 'none',
      expiresAt: new Date(expiresAt).toISOString(),
      ts: new Date().toISOString()
    }));

    if (customerEmail) {
      const emailResult = await sendDownloadEmail(customerEmail, planName, downloadUrl, expiresAt);
      if (!emailResult.success) {
        console.warn('Email not delivered:', JSON.stringify(emailResult));
      }
    } else {
      console.warn('No customer email on session', session.id);
    }
  }

  return { statusCode: 200, body: JSON.stringify({ received: true }) };
};
