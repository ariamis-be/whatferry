"""Serve the wizard on this computer only.

The page can decrypt chat backups, so the server only answers when all three
checks pass:

- it listens on 127.0.0.1, never on a network interface;
- the Host header must name that address (or localhost) and port, which
  stops a web page on another site reaching it through DNS rebinding;
- every request carries a random token, given once in the URL that opens
  the page and then sent as a header; other users and other sites never see it.

Responses forbid caching, framing, referrers and any script or style that is
not the wizard's own. Requests are not logged: a request line can hold the
token, and bodies hold keys.
"""

import hmac
import json
import secrets
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, unquote, urlsplit

from whatferry import workdir
from whatferry.ui.wizard import USER_ERRORS, Wizard

STATIC = files("whatferry.ui") / "static"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
}
SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                                "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; "
                                "frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
TOKEN_HEADER = "X-Whatferry-Token"
MAX_JSON = 64 * 1024
MAX_UPLOAD = 8 * 1024 ** 3
CHUNK = 1024 * 1024


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, wizard: Wizard, port: int = 0):
        self.wizard = wizard
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"


class Handler(BaseHTTPRequestHandler):
    server: Server
    protocol_version = "HTTP/1.1"
    server_version = "whatferry"
    sys_version = ""

    def log_message(self, format, *args):
        pass

    # Routing

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method: str):
        url = urlsplit(self.path)
        if not self._host_allowed():
            return self._send_text(HTTPStatus.MISDIRECTED_REQUEST, "wrong host")
        if method == "GET" and url.path == "/":
            given = parse_qs(url.query).get("t", [""])[0]
            if not self._token_matches(given):
                return self._send_text(HTTPStatus.FORBIDDEN,
                                       "Open the wizard with the link `whatferry ui` printed.")
            return self._send_static("index.html")
        if method == "GET" and url.path.startswith("/static/"):
            return self._send_static(url.path.removeprefix("/static/"))
        if url.path.startswith("/api/"):
            if not self._token_matches(self.headers.get(TOKEN_HEADER, "")):
                return self._send_json(HTTPStatus.FORBIDDEN, {"error": "missing or wrong token"})
            if method == "POST" and self.headers.get("Origin") not in (None, *self._origins()):
                return self._send_json(HTTPStatus.FORBIDDEN, {"error": "wrong origin"})
            route = ROUTES.get((method, url.path))
            if route is None and method == "GET" and url.path.startswith("/api/jobs/"):
                return self._job(url.path.removeprefix("/api/jobs/"))
            if route is None:
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "no such endpoint"})
            try:
                return route(self)
            except USER_ERRORS as e:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
            except (ValueError, KeyError, TypeError) as e:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"bad request: {e}"})
        return self._send_text(HTTPStatus.NOT_FOUND, "not found")

    def _origins(self) -> tuple[str, ...]:
        port = self.server.port
        return f"http://127.0.0.1:{port}", f"http://localhost:{port}"

    def _host_allowed(self) -> bool:
        port = self.server.port
        return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _token_matches(self, given: str) -> bool:
        return hmac.compare_digest(given.encode(), self.server.token.encode())

    # Endpoints

    def _overview(self):
        self._send_json(HTTPStatus.OK, self.server.wizard.overview())

    def _android_candidates(self):
        self._send_json(HTTPStatus.OK, {"files": self.server.wizard.android_candidates()})

    def _android_upload(self):
        length = int(self.headers.get("Content-Length", "-1"))
        if not 0 < length <= MAX_UPLOAD:
            return self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE if length > 0 else HTTPStatus.LENGTH_REQUIRED,
                                   {"error": "upload size missing or too large"})
        target = self.server.wizard.android_upload_target(unquote(self.headers.get("X-Filename", "")))
        remaining = length
        with workdir.open_private(target) as out:
            while remaining:
                chunk = self.rfile.read(min(CHUNK, remaining))
                if not chunk:
                    raise ValueError("upload ended early")
                out.write(chunk)
                remaining -= len(chunk)
        self._send_json(HTTPStatus.OK, {"path": str(target), "name": target.name, "size": length})

    def _android_inspect(self):
        body = self._read_json()
        wizard = self.server.wizard
        job = wizard.jobs.start(lambda: wizard.android_inspect(body["path"], body.get("key")))
        self._send_json(HTTPStatus.ACCEPTED, {"job": job})

    def _phone(self):
        self._send_json(HTTPStatus.OK, self.server.wizard.phone())

    def _phone_pull(self):
        body = self._read_json()
        wizard = self.server.wizard
        job = wizard.jobs.start(lambda: wizard.phone_pull(body["serial"], body["path"]))
        self._send_json(HTTPStatus.ACCEPTED, {"job": job})

    def _ios_backups(self):
        self._send_json(HTTPStatus.OK, self.server.wizard.ios_backups())

    def _ios_inspect(self):
        body = self._read_json()
        wizard = self.server.wizard
        job = wizard.jobs.start(lambda: wizard.ios_inspect(body["folder"], body.get("passphrase"), body["role"]))
        self._send_json(HTTPStatus.ACCEPTED, {"job": job})

    def _checklist(self):
        body = self._read_json()
        self._send_json(HTTPStatus.OK, {"checklist": self.server.wizard.set_checklist(body["item"], body["done"])})

    def _select_android(self):
        self.server.wizard.select_android(self._read_json()["key"])
        self._send_json(HTTPStatus.OK, {})

    def _destination(self):
        self.server.wizard.set_destination(self._read_json()["choice"])
        self._send_json(HTTPStatus.OK, {})

    def _step(self):
        self.server.wizard.set_step(self._read_json()["step"])
        self._send_json(HTTPStatus.OK, {})

    def _reset(self):
        self.server.wizard.reset()
        self._send_json(HTTPStatus.OK, {})

    def _settings(self):
        self._send_json(HTTPStatus.OK, self.server.wizard.settings.get())

    def _set_settings(self):
        self._send_json(HTTPStatus.OK, self.server.wizard.set_settings(self._read_json()))

    def _summary(self):
        self._send_json(HTTPStatus.OK, {"text": self.server.wizard.summary()})

    def _job(self, job_id: str):
        job = self.server.wizard.jobs.get(job_id)
        if job is None:
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "no such job"})
        self._send_json(HTTPStatus.OK, job)

    # Plumbing

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_JSON:
            raise ValueError("body missing or too large")
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            raise ValueError("expected application/json")
        body = json.loads(self.rfile.read(length))
        if not isinstance(body, dict):
            raise ValueError("expected a JSON object")
        return body

    def _send_static(self, name: str):
        resource = STATIC.joinpath(name)
        suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        if "/" in name or "\\" in name or name.startswith(".") or suffix not in CONTENT_TYPES \
                or not resource.is_file():
            return self._send_text(HTTPStatus.NOT_FOUND, "not found")
        self._send(HTTPStatus.OK, resource.read_bytes(), CONTENT_TYPES[suffix])

    def _send_json(self, status: HTTPStatus, data):
        self._send(status, json.dumps(data, default=str).encode(), "application/json")

    def _send_text(self, status: HTTPStatus, text: str):
        self._send(status, text.encode(), "text/plain; charset=utf-8")

    def _send(self, status: HTTPStatus, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # One request per connection: a refused request's unread body can
        # then never be mistaken for the next request.
        self.send_header("Connection", "close")
        self.close_connection = True
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


ROUTES = {
    ("GET", "/api/overview"): Handler._overview,
    ("GET", "/api/android/candidates"): Handler._android_candidates,
    ("POST", "/api/android/upload"): Handler._android_upload,
    ("POST", "/api/android/inspect"): Handler._android_inspect,
    ("GET", "/api/android/phone"): Handler._phone,
    ("POST", "/api/android/phone/pull"): Handler._phone_pull,
    ("GET", "/api/ios/backups"): Handler._ios_backups,
    ("POST", "/api/ios/inspect"): Handler._ios_inspect,
    ("POST", "/api/checklist"): Handler._checklist,
    ("POST", "/api/step"): Handler._step,
    ("POST", "/api/destination"): Handler._destination,
    ("POST", "/api/android/select"): Handler._select_android,
    ("POST", "/api/reset"): Handler._reset,
    ("GET", "/api/summary"): Handler._summary,
    ("GET", "/api/settings"): Handler._settings,
    ("POST", "/api/settings"): Handler._set_settings,
}


def serve(port: int = 0, open_browser: bool = True) -> None:
    server = Server(Wizard(), port)
    print(f"whatferry wizard: {server.url}")
    print("Only this computer can reach it. Press Ctrl+C to stop.", flush=True)
    if open_browser:
        threading.Timer(0.3, webbrowser.open, (server.url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
    finally:
        server.server_close()
