#!/usr/bin/env python3
"""
Local dev server for mani_website.
Serves static files AND proxies RSS feeds to avoid CORS issues.

Usage:  python3 server.py
Then open: http://localhost:8080
"""

import http.server
import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
from datetime import datetime

PORT = 8080

NS = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'dc':      'http://purl.org/dc/elements/1.1/',
    'atom':    'http://www.w3.org/2005/Atom',
}

FEEDS = {
    'substack': 'https://manikhanuja.substack.com/feed',
    # LinkedIn has no public RSS — we surface a curated fallback instead
}

def fetch_rss(url):
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; personal-site-server/1.0)'}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read()

def parse_rss(xml_bytes):
    root = ET.fromstring(xml_bytes)
    channel = root.find('channel')
    items = []
    for item in (channel.findall('item') if channel is not None else root.findall('.//item'))[:3]:
        def t(tag, ns=None):
            el = item.find(f'{{{ns}}}{tag}' if ns else tag)
            return (el.text or '').strip() if el is not None else ''

        desc = t('encoded', NS['content']) or t('description')
        # Strip HTML tags simply
        import re
        clean = re.sub(r'<[^>]+>', '', desc).strip()
        excerpt = clean[:200] + ('...' if len(clean) > 200 else '')

        pub = t('pubDate')
        try:
            year = str(datetime.strptime(pub, '%a, %d %b %Y %H:%M:%S %z').year)
        except Exception:
            year = '2026'

        items.append({
            'title':   t('title'),
            'link':    t('link'),
            'year':    year,
            'excerpt': excerpt,
        })
    return items

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == '/api/feed':
            params = urllib.parse.parse_qs(parsed.query)
            source = params.get('source', ['substack'])[0]
            url = FEEDS.get(source)
            if not url:
                self.send_response(404)
                self.end_headers()
                return
            try:
                xml_bytes = fetch_rss(url)
                items = parse_rss(xml_bytes)
                body = json.dumps({'ok': True, 'items': items}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                body = json.dumps({'ok': False, 'error': str(e)}).encode()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, fmt, *args):
        # Suppress noisy logs for static files, show API calls
        if '/api/' in args[0]:
            print(f'[server] {fmt % args}')

if __name__ == '__main__':
    import os, webbrowser, threading
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f'Serving at http://localhost:{PORT}')
    print('Press Ctrl+C to stop.\n')
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    with http.server.ThreadingHTTPServer(('', PORT), Handler) as httpd:
        httpd.serve_forever()
