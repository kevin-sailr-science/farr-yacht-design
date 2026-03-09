/**
 * join-waitlist.js
 * Netlify Function - Waitlist Entry Handler (backup to Netlify Forms)
 *
 * POST /.netlify/functions/join-waitlist
 * Body: { name, email, design, use }
 *
 * Primary channel: Netlify Forms (data-netlify="true" on the HTML form)
 * This function serves as backup + enables programmatic additions from
 * the admin dashboard or future API integrations.
 *
 * Optional: configure WAITLIST_NOTIFY_EMAIL to receive an immediate
 * notification for each waitlist entry.
 *
 * Required environment variables (all optional for basic function):
 *   RESEND_API_KEY          - for notification emails
 *   WAITLIST_NOTIFY_EMAIL   - admin email to notify on new entries
 */

exports.handler = async function (event) {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  let entry;
  try {
    entry = JSON.parse(event.body || '{}');
  } catch (e) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid request body' }) };
  }

  const { name, email, design, use } = entry;

  /* Basic validation */
  if (!name || !email || !design) {
    return {
      statusCode: 422,
      body: JSON.stringify({ error: 'name, email, and design are required' })
    };
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return {
      statusCode: 422,
      body: JSON.stringify({ error: 'Invalid email address' })
    };
  }

  /* Log the entry (in production, write to database/KV store) */
  const record = {
    timestamp: new Date().toISOString(),
    name: String(name).slice(0, 120),
    email: String(email).slice(0, 200),
    design: String(design).slice(0, 300),
    use: String(use || 'not specified').slice(0, 100)
  };
  console.log('WAITLIST_ENTRY', JSON.stringify(record));

  /* Optional: send notification email to admin */
  if (process.env.RESEND_API_KEY && process.env.WAITLIST_NOTIFY_EMAIL) {
    try {
      await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + process.env.RESEND_API_KEY,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          from: 'Farr Design Plans <plans@farrdesign.com>',
          to: process.env.WAITLIST_NOTIFY_EMAIL,
          subject: 'New design request: ' + record.design,
          text: [
            'New design request received via farrdesign.com',
            '',
            'Name: ' + record.name,
            'Email: ' + record.email,
            'Design: ' + record.design,
            'Use: ' + record.use,
            'Time: ' + record.timestamp
          ].join('\n')
        })
      });
    } catch (notifyErr) {
      /* Non-fatal -- log but don't fail the request */
      console.error('Notification email failed:', notifyErr.message);
    }
  }

  /* Optional: also submit to Netlify Forms API for consolidated view */
  /* This is handled automatically if the HTML form has data-netlify="true" */

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ success: true, message: 'Request received. We will be in touch within 2-3 business days.' })
  };
};
