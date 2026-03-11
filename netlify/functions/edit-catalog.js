/**
 * edit-catalog.js
 * Netlify Function — Catalog CRUD via GitHub Contents API
 *
 * GET  /.netlify/functions/edit-catalog           → full catalog + SHA
 * GET  /.netlify/functions/edit-catalog?design=395 → single design + SHA
 * PUT  /.netlify/functions/edit-catalog           → update one design
 * POST /.netlify/functions/edit-catalog           → add new design
 *
 * All mutating endpoints require Netlify Identity JWT with admin role.
 * Uses optimistic concurrency via SHA (GitHub's content SHA).
 *
 * Env vars required:
 *   GITHUB_TOKEN  — Personal access token with repo scope
 *   GITHUB_OWNER  — GitHub org/user (default: kevin-sailr-science)
 *   GITHUB_REPO   — Repo name (default: farr-yacht-design)
 */

const GITHUB_OWNER = process.env.GITHUB_OWNER || 'kevin-sailr-science';
const GITHUB_REPO = process.env.GITHUB_REPO || 'farr-yacht-design';
const FILE_PATH = '_data/boats.json';

/* ── Auth (same pattern as save-inventory.js) ── */

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

/* ── GitHub API helpers ── */

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

async function readBoatsJson() {
  const res = await githubFetch(FILE_PATH);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`GitHub read failed (${res.status}): ${err}`);
  }
  const data = await res.json();
  const content = Buffer.from(data.content, 'base64').toString('utf-8');
  return { boats: JSON.parse(content), sha: data.sha };
}

async function writeBoatsJson(boats, sha, commitMessage) {
  const json = JSON.stringify(boats, null, 2);
  const res = await githubFetch(FILE_PATH, {
    method: 'PUT',
    body: JSON.stringify({
      message: commitMessage,
      content: Buffer.from(json).toString('base64'),
      sha: sha
    })
  });
  if (!res.ok) {
    const err = await res.text();
    if (res.status === 409) {
      return { conflict: true, error: err };
    }
    throw new Error(`GitHub write failed (${res.status}): ${err}`);
  }
  const data = await res.json();
  return { conflict: false, newSha: data.content.sha };
}

/* ── Compute catalog stats ── */

function computeStats(boats) {
  const visible = boats.filter(b => !b.hidden);
  return {
    total: boats.length,
    visible: visible.length,
    tier1: visible.filter(b => b.tier === 1).length,
    tier2: visible.filter(b => b.tier === 2).length,
    tier3: visible.filter(b => b.tier === 3).length,
    withImages: visible.filter(b => b.images && b.images.main).length,
    withBuilder: visible.filter(b => b.builder).length,
    purchasable: visible.filter(b => b.planId).length
  };
}

/* ── Generate slug from design number ── */

function generateSlug(designNumber) {
  return String(designNumber)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/* ── CORS headers ── */

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Allow-Methods': 'GET, PUT, POST, OPTIONS',
  'Content-Type': 'application/json'
};

/* ── Handler ── */

exports.handler = async function (event) {
  /* CORS preflight */
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: CORS, body: '' };
  }

  try {
    /* ── GET: Read catalog ── */
    if (event.httpMethod === 'GET') {
      const params = event.queryStringParameters || {};
      const { boats, sha } = await readBoatsJson();

      if (params.design) {
        const design = boats.find(b =>
          String(b.designNumber) === String(params.design)
        );
        if (!design) {
          return {
            statusCode: 404,
            headers: CORS,
            body: JSON.stringify({ error: `Design ${params.design} not found` })
          };
        }
        return {
          statusCode: 200,
          headers: CORS,
          body: JSON.stringify({ design, sha })
        };
      }

      return {
        statusCode: 200,
        headers: CORS,
        body: JSON.stringify({
          designs: boats,
          sha,
          stats: computeStats(boats)
        })
      };
    }

    /* ── PUT: Update one design ── */
    if (event.httpMethod === 'PUT') {
      const user = getAdminUser(event);
      if (!user) {
        return {
          statusCode: 403,
          headers: CORS,
          body: JSON.stringify({ error: 'Admin access required.' })
        };
      }

      let body;
      try {
        body = JSON.parse(event.body || '{}');
      } catch (e) {
        return { statusCode: 400, headers: CORS, body: JSON.stringify({ error: 'Invalid JSON' }) };
      }

      const { designNumber, sha, fields } = body;
      if (!designNumber || !sha || !fields) {
        return {
          statusCode: 400,
          headers: CORS,
          body: JSON.stringify({ error: 'Required: designNumber, sha, fields' })
        };
      }

      /* Read current state from GitHub */
      const current = await readBoatsJson();

      /* Find design */
      const idx = current.boats.findIndex(b =>
        String(b.designNumber) === String(designNumber)
      );
      if (idx === -1) {
        return {
          statusCode: 404,
          headers: CORS,
          body: JSON.stringify({ error: `Design ${designNumber} not found` })
        };
      }

      /* Merge fields (only update provided fields) */
      const updated = { ...current.boats[idx], ...fields };
      current.boats[idx] = updated;

      /* Write back */
      const result = await writeBoatsJson(
        current.boats,
        sha,
        `Update design ${designNumber} via admin portal (${user.email})`
      );

      if (result.conflict) {
        return {
          statusCode: 409,
          headers: CORS,
          body: JSON.stringify({
            error: 'Conflict — boats.json was modified since you loaded it. Please refresh and try again.',
            code: 'CONFLICT'
          })
        };
      }

      return {
        statusCode: 200,
        headers: CORS,
        body: JSON.stringify({
          success: true,
          sha: result.newSha,
          message: `Updated design ${designNumber} (${updated.name || designNumber})`
        })
      };
    }

    /* ── POST: Add new design ── */
    if (event.httpMethod === 'POST') {
      const user = getAdminUser(event);
      if (!user) {
        return {
          statusCode: 403,
          headers: CORS,
          body: JSON.stringify({ error: 'Admin access required.' })
        };
      }

      let body;
      try {
        body = JSON.parse(event.body || '{}');
      } catch (e) {
        return { statusCode: 400, headers: CORS, body: JSON.stringify({ error: 'Invalid JSON' }) };
      }

      const { sha, design } = body;
      if (!sha || !design || !design.designNumber) {
        return {
          statusCode: 400,
          headers: CORS,
          body: JSON.stringify({ error: 'Required: sha, design (with designNumber)' })
        };
      }

      /* Read current state */
      const current = await readBoatsJson();

      /* Check for duplicate */
      const exists = current.boats.some(b =>
        String(b.designNumber) === String(design.designNumber)
      );
      if (exists) {
        return {
          statusCode: 409,
          headers: CORS,
          body: JSON.stringify({
            error: `Design ${design.designNumber} already exists`,
            code: 'DUPLICATE'
          })
        };
      }

      /* Populate defaults */
      const newDesign = {
        designNumber: design.designNumber,
        name: design.name || null,
        title: design.title || String(design.designNumber),
        slug: design.slug || generateSlug(design.designNumber),
        year: design.year || null,
        tier: design.tier || 1,
        planStatus: design.planStatus || 'coming_soon',
        hidden: design.hidden || false,
        hasCardPDF: design.hasCardPDF || false,
        category: design.category || [],
        designType: design.designType || null,
        designRule: design.designRule || null,
        classification: design.classification || null,
        builder: design.builder || null,
        owner: design.owner || null,
        hullConstruction: design.hullConstruction || null,
        keelType: design.keelType || null,
        rigType: design.rigType || null,
        rigMaterial: design.rigMaterial || null,
        hullsBuilt: design.hullsBuilt || null,
        description: design.description || null,
        shortDescription: design.shortDescription || null,
        shortSummary: design.shortSummary || null,
        specs: design.specs || null,
        images: design.images || null,
        nid: design.nid || null,
        drupalAlias: design.drupalAlias || null,
        inProduction: design.inProduction || null,
        isArchived: design.isArchived || null,
        drawings: design.drawings || null,
        vppFile: design.vppFile || null,
        /* E-commerce fields */
        planId: design.planId || null,
        stripePriceEnv: design.stripePriceEnv || null,
        planPrice: design.planPrice || null,
        planDescription: design.planDescription || null,
        planContents: design.planContents || null,
        cardDrawingCount: design.cardDrawingCount || null,
        cardDrawingsAvailable: design.cardDrawingsAvailable || null
      };

      /* Insert sorted by designNumber (numeric where possible) */
      current.boats.push(newDesign);
      current.boats.sort((a, b) => {
        const aNum = parseInt(a.designNumber) || 0;
        const bNum = parseInt(b.designNumber) || 0;
        if (aNum !== bNum) return aNum - bNum;
        return String(a.designNumber).localeCompare(String(b.designNumber));
      });

      /* Write back */
      const result = await writeBoatsJson(
        current.boats,
        sha,
        `Add design ${design.designNumber} via admin portal (${user.email})`
      );

      if (result.conflict) {
        return {
          statusCode: 409,
          headers: CORS,
          body: JSON.stringify({
            error: 'Conflict — boats.json was modified since you loaded it. Please refresh and try again.',
            code: 'CONFLICT'
          })
        };
      }

      return {
        statusCode: 201,
        headers: CORS,
        body: JSON.stringify({
          success: true,
          sha: result.newSha,
          message: `Added design ${design.designNumber} (${newDesign.name || design.designNumber})`
        })
      };
    }

    return {
      statusCode: 405,
      headers: CORS,
      body: JSON.stringify({ error: 'Method not allowed' })
    };

  } catch (err) {
    console.error('edit-catalog error:', err);
    return {
      statusCode: 500,
      headers: CORS,
      body: JSON.stringify({ error: 'Internal error: ' + err.message })
    };
  }
};
