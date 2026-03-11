/**
 * upload-image.js
 * Netlify Function — Upload an image to the GitHub repo (images/ directory)
 *
 * POST /.netlify/functions/upload-image
 *   Body: { filename: "026_main.jpg", content: "<base64>" }
 *   Auth: Netlify Identity JWT with admin role
 *
 * Uses GitHub Contents API to create or update the file.
 * If a file with the same name already exists, it is overwritten (update via SHA).
 *
 * Env vars required:
 *   GITHUB_TOKEN  — Personal access token with repo scope
 *   GITHUB_OWNER  — GitHub org/user (default: kevin-sailr-science)
 *   GITHUB_REPO   — Repo name (default: farr-yacht-design)
 */

const GITHUB_OWNER = process.env.GITHUB_OWNER || 'kevin-sailr-science';
const GITHUB_REPO = process.env.GITHUB_REPO || 'farr-yacht-design';
const IMAGE_DIR = 'images';

/* ── Auth (same pattern as edit-catalog.js) ── */

function getAdminUser(event) {
  const auth = (event.headers && event.headers['authorization']) || '';
  if (!auth.startsWith('Bearer ')) return null;
  const token = auth.slice(7);
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'));
    const roles = (payload.app_metadata && payload.app_metadata.roles) || [];
    if (!roles.includes('admin')) return null;
    return { email: payload.email || payload.sub, roles };
  } catch (e) {
    return null;
  }
}

/* ── GitHub API helper ── */

async function githubFetch(path, options = {}) {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new Error('GITHUB_TOKEN env var not set');

  const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      ...(options.headers || {})
    }
  });
  return res;
}

/* ── CORS headers ── */

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Content-Type': 'application/json'
};

/* ── Handler ── */

exports.handler = async function (event) {
  /* CORS preflight */
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: CORS, body: '' };
  }

  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers: CORS,
      body: JSON.stringify({ error: 'Method not allowed' })
    };
  }

  try {
    /* Auth check */
    const user = getAdminUser(event);
    if (!user) {
      return {
        statusCode: 401,
        headers: CORS,
        body: JSON.stringify({ error: 'Unauthorized — admin role required' })
      };
    }

    const body = JSON.parse(event.body || '{}');
    const { filename, content } = body;

    if (!filename || !content) {
      return {
        statusCode: 400,
        headers: CORS,
        body: JSON.stringify({ error: 'filename and content (base64) are required' })
      };
    }

    /* Validate filename — only allow safe image filenames */
    if (!/^[\w\-]+\.(jpg|jpeg|png|webp)$/i.test(filename)) {
      return {
        statusCode: 400,
        headers: CORS,
        body: JSON.stringify({ error: 'Invalid filename. Use alphanumeric with .jpg/.png/.webp extension.' })
      };
    }

    /* Check base64 size (roughly: base64 is ~4/3 of original, limit to ~5MB original) */
    const sizeBytes = Math.ceil(content.length * 3 / 4);
    if (sizeBytes > 6 * 1024 * 1024) { /* allow some overhead */
      return {
        statusCode: 400,
        headers: CORS,
        body: JSON.stringify({ error: 'Image too large (max 5 MB)' })
      };
    }

    const filePath = `${IMAGE_DIR}/${filename}`;

    /* Check if file already exists (need its SHA to update) */
    let existingSha = null;
    const checkRes = await githubFetch(filePath);
    if (checkRes.ok) {
      const existing = await checkRes.json();
      existingSha = existing.sha;
    }

    /* Create or update the file */
    const putBody = {
      message: `Upload image: ${filename} (via admin portal by ${user.email})`,
      content: content /* already base64 */
    };
    if (existingSha) {
      putBody.sha = existingSha; /* required for update */
    }

    const putRes = await githubFetch(filePath, {
      method: 'PUT',
      body: JSON.stringify(putBody)
    });

    if (!putRes.ok) {
      const errText = await putRes.text();
      throw new Error(`GitHub upload failed (${putRes.status}): ${errText}`);
    }

    const result = await putRes.json();

    return {
      statusCode: 200,
      headers: CORS,
      body: JSON.stringify({
        success: true,
        filename: filename,
        sha: result.content.sha,
        size: result.content.size,
        url: result.content.html_url
      })
    };

  } catch (err) {
    console.error('upload-image error:', err);
    return {
      statusCode: 500,
      headers: CORS,
      body: JSON.stringify({ error: err.message })
    };
  }
};
