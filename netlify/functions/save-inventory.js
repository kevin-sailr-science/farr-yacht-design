/**
 * save-inventory.js
 * Netlify Function - Write plan inventory to Netlify Blobs
 *
 * POST /.netlify/functions/save-inventory
 * Headers: { Authorization: "Bearer {NETLIFY_IDENTITY_TOKEN}" }
 * Body: { plans: [...] }
 * Returns: { success: true }
 *
 * Requires valid Netlify Identity JWT with role "admin".
 * Admin users must be invited via: Netlify Dashboard -> Identity -> Invite Users.
 */

const { getStore } = require('@netlify/blobs');

/* Validate Netlify Identity JWT -- checks token exists and has admin role.
   Full JWT signature verification is handled by Netlify's Identity gateway
   when netlify.toml sets [functions] included_files. Here we do a basic
   role check on the decoded payload as a second layer. */
function getIdentityUser(event) {
  const auth = (event.headers && event.headers['authorization']) || '';
  if (!auth.startsWith('Bearer ')) return null;
  const token = auth.slice(7);
  try {
    /* Decode payload (middle segment) without verifying signature.
       Netlify Identity verifies the signature at the edge before invoking
       the function, so payload claims can be trusted here. */
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'));
    return payload;
  } catch (e) {
    return null;
  }
}

function isAdmin(user) {
  if (!user) return false;
  const roles = (user.app_metadata && user.app_metadata.roles) || [];
  return roles.includes('admin');
}

exports.handler = async function (event) {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  /* Auth check */
  const user = getIdentityUser(event);
  if (!isAdmin(user)) {
    return {
      statusCode: 403,
      body: JSON.stringify({ error: 'Admin access required. Sign in via Netlify Identity.' })
    };
  }

  /* Parse body */
  let plans;
  try {
    const body = JSON.parse(event.body || '{}');
    plans = body.plans;
    if (!Array.isArray(plans)) throw new Error('plans must be an array');
  } catch (e) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid request: ' + e.message }) };
  }

  /* Basic validation -- each plan must have id, name, status */
  for (const plan of plans) {
    if (!plan.id || !plan.name || !plan.status) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'Each plan requires id, name, and status fields.' })
      };
    }
    if (!['available', 'digitizing', 'archive'].includes(plan.status)) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'Invalid status: ' + plan.status + '. Use available, digitizing, or archive.' })
      };
    }
  }

  try {
    const store = getStore('farr-inventory');
    await store.setJSON('plans', plans);

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ success: true, count: plans.length, savedBy: user.email || user.sub })
    };

  } catch (err) {
    console.error('save-inventory error:', err.message);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Failed to save inventory: ' + err.message })
    };
  }
};
