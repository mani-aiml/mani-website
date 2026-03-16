"""
Netlify Python serverless function to fetch and parse RSS feeds.
Handles CORS and returns JSON format suitable for the frontend.
"""

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

FEEDS = {
    'substack': 'https://manikhanuja.substack.com/feed',
}

NS = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'atom': 'http://www.w3.org/2005/Atom',
}


def fetch_rss(url):
    """Fetch RSS feed from URL with proper headers."""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; netlify-function/1.0)'}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read()


def parse_rss(xml_bytes):
    """Parse RSS XML and extract items."""
    root = ET.fromstring(xml_bytes)
    channel = root.find('channel')
    items = []

    for item in (channel.findall('item') if channel is not None else root.findall('.//item'))[:3]:
        def t(tag, ns=None):
            el = item.find(f'{{{ns}}}{tag}' if ns else tag)
            return (el.text or '').strip() if el is not None else ''

        desc = t('encoded', NS['content']) or t('description')

        # Strip HTML tags
        import re
        clean = re.sub(r'<[^>]+>', '', desc).strip()
        excerpt = clean[:200] + ('...' if len(clean) > 200 else '')

        pub = t('pubDate')
        try:
            year = str(datetime.strptime(pub, '%a, %d %b %Y %H:%M:%S %z').year)
        except Exception:
            year = '2026'

        items.append({
            'title': t('title'),
            'link': t('link'),
            'year': year,
            'excerpt': excerpt,
        })

    return items


def handler(event, context):
    """Netlify function handler for RSS feed endpoint."""
    try:
        # Get source from query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        source = query_params.get('source', 'substack')

        # Get the feed URL
        url = FEEDS.get(source)
        if not url:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'ok': False, 'error': f'Unknown source: {source}'})
            }

        # Fetch and parse the feed
        xml_bytes = fetch_rss(url)
        items = parse_rss(xml_bytes)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'ok': True, 'items': items})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'ok': False, 'error': str(e)})
        }
