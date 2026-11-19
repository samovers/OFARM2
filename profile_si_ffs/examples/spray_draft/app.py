"""Loopback-only draft rehearsal. There are no production or publish routes."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from draft import HERE, ID, GATES, capture_shape, check_capture, sha, strict_json, utc_now
from verifier import Verifier

MAX_BODY = 16384
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8'),
          '/sw.js': ('sw.js', 'text/javascript; charset=utf-8')}


class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class DraftInbox:
    def __init__(self, path, catalog_path=HERE / 'catalog.json', *, verifier=None):
        self.path, self.catalog_path = Path(path), Path(catalog_path)
        self.verifier = verifier if verifier is not None else Verifier()
        self.verifier_directory = self.path.with_suffix('.verifier-results')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS captures (
                    id TEXT PRIMARY KEY, original BLOB NOT NULL,
                    sha256 TEXT NOT NULL, received_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS acknowledgements (
                    id TEXT PRIMARY KEY REFERENCES captures(id),
                    original_sha256 TEXT NOT NULL, reviewed_at TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys = ON')
            with db:
                yield db
        finally:
            db.close()

    def catalog(self):
        raw = self.catalog_path.read_bytes()
        return {'catalog': strict_json(raw), 'sha256': sha(raw)}

    def save(self, raw):
        capture = capture_shape(raw)
        digest = sha(raw)
        with self.connect() as db:
            # One atomic insert. A retry can never replace the original bytes.
            db.execute('INSERT OR IGNORE INTO captures VALUES (?, ?, ?, ?)',
                       (capture['draftId'], raw, digest, utc_now()))
            saved = db.execute('SELECT original FROM captures WHERE id = ?', (capture['draftId'],)).fetchone()
            if bytes(saved['original']) != raw:
                raise Problem(409, 'This draft ID already belongs to another entry. The saved original was not changed.')
        return self.read(capture['draftId'])

    def read(self, draft_id, *, expected_sha=None):
        with self.connect() as db:
            row = db.execute('SELECT * FROM captures WHERE id = ?', (draft_id,)).fetchone()
            review = db.execute('SELECT * FROM acknowledgements WHERE id = ?', (draft_id,)).fetchone()
        if row is None:
            raise Problem(404, 'Draft not found on this computer. Your browser may still have an unsynced copy.')
        raw = bytes(row['original'])
        if sha(raw) != row['sha256']:
            raise Problem(409, 'The saved original has changed. Review is blocked.')
        if expected_sha is not None and expected_sha != row['sha256']:
            raise Problem(409, 'This screen no longer matches the saved original. Reload the draft.')
        if review and review['original_sha256'] != row['sha256']:
            raise Problem(409, 'The review does not match this original. Review is blocked.')
        catalog_raw = self.catalog_path.read_bytes()
        capture = capture_shape(raw)
        catalog_sha = capture['catalogSha256']
        # Preserve previous drafts against the exact list they used. An
        # unknown or damaged list never silently becomes the current list.
        if (sha(catalog_raw) != catalog_sha and self.catalog_path.resolve() == HERE / 'catalog.json'
                and re.fullmatch('[0-9a-f]{64}', catalog_sha)):
            archived = HERE / 'catalogs' / (catalog_sha + '.json')
            if archived.is_file():
                catalog_raw = archived.read_bytes()
                if sha(catalog_raw) != catalog_sha:
                    raise Problem(409, 'The saved example list has changed. The original draft is kept; its checks are blocked.')
        result = check_capture(raw, catalog_raw, row['received_at'])
        result.update(originalText=raw.decode('utf-8'), reviewedAt=review['reviewed_at'] if review else None)
        result['verification'] = self.verifier.check(result, self.verifier_directory)
        return result

    def acknowledge(self, draft_id, raw):
        request = strict_json(raw)
        if type(request) is not dict or set(request) != {'originalSha256'} or type(request['originalSha256']) is not str:
            raise Problem(400, 'Draft review accepts only the original entry digest.')
        result = self.read(draft_id, expected_sha=request['originalSha256'])
        if not result['canAcknowledgeDraft']:
            raise Problem(409, 'Check the highlighted entry problems before finishing draft review.')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO acknowledgements VALUES (?, ?, ?)',
                       (draft_id, result['originalSha256'], utc_now()))
        return self.read(draft_id)


def make_server(port=8765, data_path=None, catalog_path=HERE / 'catalog.json', *, verifier=None):
    inbox = DraftInbox(data_path or HERE / '.local/drafts.sqlite3', catalog_path, verifier=verifier)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # No capture content or identifiers in the console log.

        def reply(self, status, value, content_type='application/json; charset=utf-8'):
            raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; worker-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def guard(self):
            port = self.server.server_port
            expected_host = '127.0.0.1:' + str(port)
            if self.headers.get('Host') != expected_host:
                raise Problem(403, 'Use the 127.0.0.1 address printed by this test app.')
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + expected_host:
                raise Problem(403, 'Another website cannot write to this local draft inbox.')
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                raise Problem(403, 'Cross-site access is not available.')

        def body(self):
            if self.headers.get('Transfer-Encoding'):
                raise Problem(400, 'Use a complete JSON request.')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise Problem(415, 'Send a JSON draft.')
            try:
                length = int(self.headers.get('Content-Length', '-1'))
            except ValueError:
                raise Problem(400, 'Invalid request length.')
            if not 0 < length <= MAX_BODY:
                raise Problem(413, 'The draft is empty or too large.')
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise Problem(400, 'The draft was not received in full.')
            return raw

        def handle_request(self, method):
            try:
                self.guard()
                path = urlsplit(self.path).path
                if method == 'GET' and path in ASSETS:
                    filename, content_type = ASSETS[path]
                    return self.reply(200, (HERE / 'web' / filename).read_bytes(), content_type)
                if method == 'GET' and path == '/api/catalog':
                    return self.reply(200, inbox.catalog())
                if method == 'POST' and path == '/api/drafts':
                    return self.reply(200, inbox.save(self.body()))
                parts = path.strip('/').split('/')
                if len(parts) in (3, 4) and parts[:2] == ['api', 'drafts'] and ID.fullmatch(parts[2]):
                    if method == 'GET' and len(parts) == 3:
                        return self.reply(200, inbox.read(parts[2]))
                    if method == 'POST' and len(parts) == 4 and parts[3] == 'review':
                        return self.reply(200, inbox.acknowledge(parts[2], self.body()))
                    if method == 'POST' and len(parts) == 4 and parts[3] == 'verify':
                        request = strict_json(self.body())
                        if type(request) is not dict or set(request) != {'originalSha256'} or type(request['originalSha256']) is not str:
                            raise Problem(400, 'Supply only the original draft digest for a recheck.')
                        result = inbox.read(parts[2], expected_sha=request['originalSha256'])
                        return self.reply(200, result)
                if path.startswith(('/commit', '/review', '/publish', '/api/publish', '/api/accept', '/views')):
                    return self.reply(403, {'error': 'Real approval and publication are unavailable in this draft app.', 'gates': GATES})
                raise Problem(404, 'This test app has no such route.')
            except Problem as exc:
                self.reply(exc.status, {'error': exc.message, 'gates': GATES})
            except (ValueError, UnicodeError) as exc:
                self.reply(400, {'error': str(exc), 'gates': GATES})
            except (sqlite3.Error, OSError, RuntimeError):
                self.reply(503, {'error': 'The draft could not be read or saved safely. Keep the browser copy and retry.', 'gates': GATES})

        def do_GET(self):
            self.handle_request('GET')

        def do_POST(self):
            self.handle_request('POST')

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.inbox = inbox
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Local spray draft rehearsal; no real approval or publication.')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', type=Path, help='Disposable local draft database.')
    args = parser.parse_args()
    server = make_server(args.port, args.data)
    print(f'Draft test app: http://127.0.0.1:{server.server_port}', flush=True)
    print('Fictional data only. Real approval and publication stay blocked.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
