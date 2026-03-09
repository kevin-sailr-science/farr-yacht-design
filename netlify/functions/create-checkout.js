/**
 * create-checkout.js
 * Netlify Function - Stripe Checkout Session Creator
 *
 * POST /.netlify/functions/create-checkout
 * Body: { planId: "farr-40-full" }
 * Returns: { url: "https://checkout.stripe.com/..." }
 *
 * Required environment variables (set in Netlify UI):
 *   STRIPE_SECRET_KEY   - sk_live_... or sk_test_...
 *   SITE_URL            - https://farrdesign.com (no trailing slash)
 *
 * Demo/client-review mode (no Stripe keys required):
 *   STRIPE_MOCK=true    - bypasses Stripe, redirects to success page with mock session
 */

const PLAN_CATALOG = {
  'farr-40-full': {
    name: 'Farr 40 One-Design — Full Plan Set',
    priceId: process.env.STRIPE_PRICE_FARR40 || 'price_PLACEHOLDER_farr40',
    description: 'Sail plan, lines drawing, deck layout, rig specification, appendage detail.',
    price: 350
  },
  'farr-1020-full': {
    name: 'Farr 1020 — Full Plan Set',
    priceId: process.env.STRIPE_PRICE_FARR1020 || 'price_PLACEHOLDER_farr1020',
    description: 'Brochure, design comments, deck layout, sail plan.',
    price: 350
  },
  'farr-1120-full': {
    name: 'Farr 1120 — Plan Set',
    priceId: process.env.STRIPE_PRICE_FARR1120 || 'price_PLACEHOLDER_farr1120',
    description: 'Original builder brochure with lines and specifications.',
    price: 250
  },
  'farr-740-sport-full': {
    name: 'Farr 740 Sport — Plan Set',
    priceId: process.env.STRIPE_PRICE_FARR740 || 'price_PLACEHOLDER_farr740',
    description: 'Brochure and sail plan.',
    price: 295
  },
  'noelex-30-full': {
    name: 'Noelex 30 — Full Plan Set',
    priceId: process.env.STRIPE_PRICE_NOELEX30 || 'price_PLACEHOLDER_noelex30',
    description: 'Two brochures (original + Noelex edition) and sail plan.',
    price: 350
  },
  'farr-92-full': {
    name: 'Farr 9.2 — Full Plan Set',
    priceId: process.env.STRIPE_PRICE_FARR92 || 'price_PLACEHOLDER_farr92',
    description: 'Deck layout, interior arrangement, sail plan, VPP analysis.',
    price: 350
  },
  'farr-920-full': {
    name: 'Farr 920 — Full Plan Set',
    priceId: process.env.STRIPE_PRICE_FARR920 || 'price_PLACEHOLDER_farr920',
    description: 'Deck layout, interior arrangement, sail plan.',
    price: 350
  },
  'farr-11s-full': {
    name: 'Farr 11S — Full Plan Set',
    priceId: process.env.STRIPE_PRICE_FARR11S || 'price_PLACEHOLDER_farr11s',
    description: 'Brochure, deck layout, sail plan.',
    price: 350
  },
  'beneteau-first-407-full': {
    name: 'Beneteau First 40.7 — Plan Set',
    priceId: process.env.STRIPE_PRICE_BEN407 || 'price_PLACEHOLDER_ben407',
    description: 'Interior layout and profile drawing.',
    price: 295
  },
  'farr-63-kiwi-spirit-full': {
    name: 'Farr 63 "Kiwi Spirit" — Plan Set',
    priceId: process.env.STRIPE_PRICE_FARR63KS || 'price_PLACEHOLDER_farr63ks',
    description: 'Promotional drawing package and specifications.',
    price: 350
  },
};

exports.handler = async function (event) {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  let planId;
  try {
    const body = JSON.parse(event.body || '{}');
    planId = body.planId;
  } catch (e) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid request body' }) };
  }

  const plan = PLAN_CATALOG[planId];
  if (!plan) {
    return { statusCode: 404, body: JSON.stringify({ error: 'Plan not found: ' + planId }) };
  }

  const siteUrl = process.env.SITE_URL || 'https://farrdesign.com';

  /* ---- MOCK MODE: set STRIPE_MOCK=true in Netlify env vars for client demos ---- */
  if (process.env.STRIPE_MOCK === 'true') {
    const mockSessionId = 'mock_session_' + Date.now() + '_' + planId.replace(/-/g, '_');
    const successUrl = siteUrl + '/purchase-success.html?session_id=' + mockSessionId;
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: successUrl })
    };
  }
  /* ---- END MOCK MODE ---- */

  const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);

  try {
    const session = await stripe.checkout.sessions.create({
      mode: 'payment',
      line_items: [{ price: plan.priceId, quantity: 1 }],
      payment_intent_data: {
        metadata: { planId: planId, planName: plan.name }
      },
      metadata: { planId: planId, planName: plan.name },
      success_url: siteUrl + '/purchase-success.html?session_id={CHECKOUT_SESSION_ID}',
      cancel_url: siteUrl + '/design-plans.html?cancelled=1',
      customer_creation: 'always',
      billing_address_collection: 'auto',
      allow_promotion_codes: false
    });

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: session.url })
    };

  } catch (err) {
    console.error('Stripe error:', err.message);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Checkout creation failed. Please try again.' })
    };
  }
};
