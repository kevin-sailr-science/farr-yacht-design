/**
 * get-inventory.js
 * Netlify Function - Read plan inventory from Netlify Blobs
 *
 * GET /.netlify/functions/get-inventory
 * Returns: { plans: [...] }
 *
 * Falls back to DEFAULT_PLANS if no blob exists yet.
 * No authentication required (inventory is public product data).
 *
 * Netlify Blobs docs: https://docs.netlify.com/blobs/overview/
 */

const { getStore } = require('@netlify/blobs');

/* Default inventory — single source of truth on first deploy.
   Once admin saves changes via Netlify Blobs, the blob supersedes this.
   Fields: id, name, boatClass, year, status, price, desc, contents[], designNumber, fileFormat */
const DEFAULT_PLANS = [
  /* ========== AVAILABLE — ready for purchase ========== */
  {
    id: 'farr-40-full',
    name: 'Farr 40 One-Design',
    boatClass: 'Grand Prix One-Design',
    year: '1996',
    status: 'available',
    price: 350,
    desc: 'The complete plan set for the Farr 40 one-design — the international grand-prix fleet raced at world championship level through the 2000s. Includes sail plan, lines drawing, deck layout, rig specification, and appendage detail.',
    contents: ['Sail Plan', 'Lines Drawing', 'Deck Layout', 'Rig Specification', 'Appendage Detail'],
    designNumber: '—',
    fileFormat: 'PDF'
  },
  {
    id: 'farr-1020-full',
    name: 'Farr 1020',
    boatClass: 'Production Racer/Cruiser',
    year: '1978',
    status: 'available',
    price: 350,
    desc: 'Design #074. The Farr 1020 (33\u2032) was one of Bruce Farr\u2019s early production designs from New Zealand — a fast, competitive IOR racer that also cruised well. This is the most comprehensive plan set in the archive with brochure, designer\u2019s comments, deck layout, and sail plan.',
    contents: ['Brochure', 'Designer\u2019s Comments', 'Deck Layout', 'Sail Plan'],
    designNumber: '074',
    fileFormat: 'PDF'
  },
  {
    id: 'farr-1120-full',
    name: 'Farr 1120',
    boatClass: 'Cruiser/Racer',
    year: '1980',
    status: 'available',
    price: 250,
    desc: 'Design #092. The Farr 1120 (37\u2032) was a popular production cruiser/racer built in New Zealand. Original builder brochure with lines and specifications.',
    contents: ['Brochure'],
    designNumber: '092',
    fileFormat: 'PDF'
  },
  {
    id: 'farr-740-sport-full',
    name: 'Farr 740 Sport',
    boatClass: 'Performance Cruiser',
    year: '1981',
    status: 'available',
    price: 295,
    desc: 'Design #101. A performance pilothouse design with exceptional sailing ability. Brochure and sail plan package.',
    contents: ['Brochure', 'Sail Plan'],
    designNumber: '101',
    fileFormat: 'PDF'
  },
  {
    id: 'noelex-30-full',
    name: 'Noelex 30',
    boatClass: 'One-Design',
    year: '1982',
    status: 'available',
    price: 350,
    desc: 'Design #112. The iconic New Zealand one-design, also known as the Farr 940. Raced in one-design fleets across Australasia for decades. Includes original brochure, Noelex edition brochure, and sail plan.',
    contents: ['Original Brochure', 'Noelex Brochure', 'Sail Plan'],
    designNumber: '112',
    fileFormat: 'PDF'
  },
  {
    id: 'farr-92-full',
    name: 'Farr 9.2',
    boatClass: 'IOR Racer/Cruiser',
    year: '1983',
    status: 'available',
    price: 350,
    desc: 'Design #128. Also known as the Farr 37 — evolved from interest by Chesapeake Bay yachtsmen for a competitive IOR Class B racer with a genuine cruising interior. The most technical plan set: deck, interior, sail plan, plus VPP performance data.',
    contents: ['Deck Layout', 'Interior Arrangement', 'Sail Plan', 'VPP Analysis'],
    designNumber: '128',
    fileFormat: 'PDF'
  },
  {
    id: 'farr-920-full',
    name: 'Farr 920',
    boatClass: 'Ocean Racing Yacht',
    year: '1983',
    status: 'available',
    price: 350,
    desc: 'Design #129. A 59-foot IOR ocean racing yacht built for serious offshore competition. Deck layout, interior arrangement, and sail plan.',
    contents: ['Deck Layout', 'Interior Arrangement', 'Sail Plan'],
    designNumber: '129',
    fileFormat: 'PDF'
  },
  {
    id: 'farr-11s-full',
    name: 'Farr 11S',
    boatClass: 'Offshore Cruiser',
    year: '1984',
    status: 'available',
    price: 350,
    desc: 'Design #137. Also known as the Farr 44. Commissioned by noted yachtsman and author Newbold Smith as a replacement for his existing boat of similar length, combining offshore cruising capability with strong sailing performance. Brochure, deck layout, and sail plan.',
    contents: ['Brochure', 'Deck Layout', 'Sail Plan'],
    designNumber: '137',
    fileFormat: 'PDF'
  },
  {
    id: 'beneteau-first-407-full',
    name: 'Beneteau First 40.7',
    boatClass: 'Production Cruiser/Racer',
    year: '1996',
    status: 'available',
    price: 295,
    desc: 'Design #354. A 40-foot cruiser/racer designed for Beneteau — one of the most successful production designs of its era, sailed in IRC and ORC fleets worldwide. Interior layout and profile drawing.',
    contents: ['Interior Layout', 'Profile Drawing'],
    designNumber: '354',
    fileFormat: 'PDF'
  },
  {
    id: 'farr-63-kiwi-spirit-full',
    name: 'Farr 63 "Kiwi Spirit"',
    boatClass: 'Solo Ocean Cruiser',
    year: '2010',
    status: 'available',
    price: 350,
    desc: 'Design #727. A 63-foot yacht designed for solo round-the-world sailing. Promotional drawing package and full specifications.',
    contents: ['Promotional Drawings', 'Specifications'],
    designNumber: '727',
    fileFormat: 'PDF'
  },
  /* ========== DIGITIZING — in the queue ========== */
  {
    id: 'farr-30-full',
    name: 'Farr 30',
    boatClass: 'One-Design',
    year: '1999',
    status: 'digitizing',
    price: 350,
    desc: 'High-performance sportboat for one-design racing. Popular in North American IRC and ORC fleets.',
    contents: ['Sail Plan', 'Lines Drawing', 'Deck Layout'],
    designNumber: '—',
    fileFormat: 'PDF'
  },
  {
    id: 'farr-25-full',
    name: 'Farr 25',
    boatClass: 'One-Design',
    year: '1994',
    status: 'digitizing',
    price: 350,
    desc: 'Entry-level Farr one-design that introduced many sailors to performance racing on both sides of the Atlantic.',
    contents: ['Sail Plan', 'Lines Drawing', 'Deck Layout'],
    designNumber: '—',
    fileFormat: 'PDF'
  },
  {
    id: 'whitbread-60-gen1',
    name: 'Whitbread 60 (Gen 1)',
    boatClass: 'Ocean Racer',
    year: '1993',
    status: 'digitizing',
    price: 350,
    desc: 'First-generation Whitbread 60 hull form designed for the 1993\u201394 Whitbread Round the World Race.',
    contents: ['Sail Plan', 'Lines Drawing', 'General Arrangement'],
    designNumber: '—',
    fileFormat: 'PDF'
  },
  {
    id: 'volvo-65-full',
    name: 'Volvo Ocean 65',
    boatClass: 'One-Design Ocean Racer',
    year: '2014',
    status: 'digitizing',
    price: 350,
    desc: 'One-design offshore racer built for the Volvo Ocean Race 2014\u201315 and beyond. Co-designed with VPLP.',
    contents: ['Sail Plan', 'Lines Drawing', 'Deck Layout', 'Appendage Drawing'],
    designNumber: '—',
    fileFormat: 'PDF'
  },
];

exports.handler = async function (event) {
  if (event.httpMethod !== 'GET') {
    return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  try {
    const store = getStore('farr-inventory');
    const blob = await store.get('plans', { type: 'json' });

    const plans = blob || DEFAULT_PLANS;

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store'
      },
      body: JSON.stringify({ plans: plans, source: blob ? 'blob' : 'default' })
    };

  } catch (err) {
    console.error('get-inventory error:', err.message);
    /* Degrade gracefully to defaults if Blobs unavailable (e.g. local dev) */
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plans: DEFAULT_PLANS, source: 'fallback', error: err.message })
    };
  }
};
