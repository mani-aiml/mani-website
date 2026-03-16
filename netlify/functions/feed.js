/**
 * Netlify JavaScript serverless function to fetch and parse the Substack RSS feed.
 * Deployed at /.netlify/functions/feed  →  proxied to /api/feed via netlify.toml
 */

const FEEDS = {
  substack: 'https://manikhanuja.substack.com/feed',
};

const CORS_HEADERS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
};

function respond(statusCode, body) {
  return { statusCode, headers: CORS_HEADERS, body: JSON.stringify(body) };
}

function stripHtml(html) {
  return (html || '').replace(/<[^>]+>/g, '').replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').trim();
}

function getTag(xml, tag, after = 0) {
  // Grab the first occurrence of <tag>...</tag> after position `after`
  const open = xml.indexOf(`<${tag}`, after);
  if (open === -1) return '';
  const close = xml.indexOf(`</${tag}>`, open);
  if (close === -1) return '';
  const inner = xml.slice(xml.indexOf('>', open) + 1, close);
  return inner.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1').trim();
}

function parseRss(xml) {
  const items = [];
  let pos = 0;

  while (items.length < 3) {
    const start = xml.indexOf('<item>', pos);
    if (start === -1) break;
    const end = xml.indexOf('</item>', start);
    if (end === -1) break;
    const chunk = xml.slice(start, end + 7);
    pos = end + 7;

    const title   = stripHtml(getTag(chunk, 'title'));
    const link    = getTag(chunk, 'link') || getTag(chunk, 'guid');
    const pubDate = getTag(chunk, 'pubDate');
    const desc    = stripHtml(
      getTag(chunk, 'content:encoded') || getTag(chunk, 'description')
    );
    const excerpt = desc.length > 220 ? desc.slice(0, 220) + '…' : desc;

    let year = '2026';
    try { year = String(new Date(pubDate).getFullYear()); } catch (_) {}

    items.push({ title, link, year, excerpt });
  }

  return items;
}

exports.handler = async (event) => {
  // Handle CORS preflight
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: CORS_HEADERS, body: '' };
  }

  try {
    const source = (event.queryStringParameters || {}).source || 'substack';
    const url = FEEDS[source];

    if (!url) {
      return respond(404, { ok: false, error: `Unknown source: ${source}` });
    }

    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; netlify-function/1.0)' },
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) {
      throw new Error(`Upstream HTTP ${res.status}`);
    }

    const xml = await res.text();
    const items = parseRss(xml);

    if (!items.length) {
      throw new Error('No items found in feed');
    }

    return respond(200, { ok: true, items });

  } catch (err) {
    console.error('feed function error:', err.message);
    return respond(500, { ok: false, error: err.message });
  }
};
