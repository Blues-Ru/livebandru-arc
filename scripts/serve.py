#!/usr/bin/env python3
"""
Dev server for liveband-site/.
Serves index.html for directory URLs, correct charset, and URL-clean paths.
"""

import http.server
import socketserver
import urllib.parse
from pathlib import Path

SITE = Path(__file__).parent.parent.parent / "liveband-site"
PORT = 8083


class LiveBandHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = urllib.parse.unquote(parsed.path)

        # Strip trailing slash for file lookup, but keep for directory
        file_path = SITE / path.lstrip('/')

        # If directory → serve index.html
        if file_path.is_dir():
            index = file_path / 'index.html'
            if index.exists():
                self.path = parsed._replace(path=path.rstrip('/') + '/index.html').geturl()
        elif not file_path.exists() and not file_path.suffix:
            # Try appending /index.html
            alt = SITE / (path.lstrip('/') + '/index.html')
            if alt.exists():
                self.path = path + '/index.html'

        super().do_GET()

    def guess_type(self, path):
        ctype = super().guess_type(path)
        if ctype.startswith('text/html'):
            return 'text/html; charset=utf-8'
        return ctype

    def send_response(self, code, message=None):
        super().send_response(code, message)
        self.send_header('Cache-Control', 'no-store')

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")


if __name__ == '__main__':
    print(f"Serving {SITE} at http://localhost:{PORT}/")
    print("Ctrl+C to stop.")
    with socketserver.TCPServer(('', PORT), LiveBandHandler) as httpd:
        httpd.allow_reuse_address = True
        httpd.serve_forever()
