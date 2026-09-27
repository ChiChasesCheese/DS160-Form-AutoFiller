"""Loopback receiver: lets a script running inside a CEAC page hand large payloads to disk.

Browser-automation tools truncate JavaScript results (~1 kB), so a whole review page cannot be read back in one
call. Instead the page first GETs http://127.0.0.1:<port>/ping (must answer `backhome-receiver`), then POSTs to
/save?name=<file>; the server writes the body into `out/<file>`. Default port 47631. It binds to loopback only, accepts a fixed set of safe file names, and answers the CORS / Private
Network Access preflight Chrome sends for public -> local requests.
"""

from __future__ import annotations

import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
ALLOWED_ORIGINS = {"https://ceac.state.gov"}
MAX_BYTES = 5 * 1024 * 1024


def make_handler(out: Path, origins: set[str] = ALLOWED_ORIGINS):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            origin = self.headers.get("Origin", "")
            if origin in origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Private-Network", "true")

        def do_GET(self):  # noqa: N802 — handshake so a page never talks to an unrelated local service
            ok = urlparse(self.path).path == "/ping"
            self.send_response(200 if ok else 404)
            self._cors()
            self.end_headers()
            if ok:
                self.wfile.write(b"backhome-receiver")

        def do_OPTIONS(self):  # noqa: N802 — http.server naming
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_POST(self):  # noqa: N802
            name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
            length = int(self.headers.get("Content-Length") or 0)
            if self.headers.get("Origin") not in origins or not SAFE_NAME.match(name) or length > MAX_BYTES:
                self.send_response(403)
                self.end_headers()
                return
            body = self.rfile.read(length)
            (out / name).write_bytes(body)
            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(f"saved {name} {len(body)}".encode())

        def log_message(self, fmt, *args):  # quiet; print one line per save instead
            if self.command == "POST":
                print(f"received {parse_qs(urlparse(self.path).query).get('name', ['?'])[0]}", flush=True)

    return Handler


DEFAULT_PORT = 47631  # uncommon on purpose: 8765 is AnkiConnect's default


def serve(out: Path, port: int = DEFAULT_PORT) -> None:
    """Refuses to start if the port is taken — a page must never POST to someone else's local service."""
    import socket

    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(f"port {port} is already in use by another program; pick another with --port")
    out.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(out))
    print(f"listening on http://127.0.0.1:{port} -> {out}", flush=True)
    server.serve_forever()
