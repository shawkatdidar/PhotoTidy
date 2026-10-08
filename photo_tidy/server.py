import json, os, platform, re, secrets, shutil, subprocess, threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from . import scan, store, groups, send, model, explore
from .paths import APP_DIR, MODEL_FILE, THUMBS

STATIC = os.path.join(os.path.dirname(__file__), "static", "index.html")
UUID_RE = send.UUID_RE


class App:
    def __init__(self, port, dry_run=False, limit=None):
        self.port, self.dry_run, self.limit = port, dry_run, limit
        self.token = secrets.token_urlsafe(24)
        self.cache = None
        self.lock = threading.Lock()
        self.activity_lock = threading.Lock()

    def vectors(self):
        con = store.connect()
        try:
            return store.load_embedded(con)
        finally:
            con.close()

    def results(self, sim):
        key = (sim, scan.state["phase"], scan.state["done"], scan.state["started"])
        with self.lock:
            if self.cache and self.cache[0] == key:
                return self.cache[1]
            meta, emb = self.vectors()
            res = groups.analyze(meta, emb, sim) if len(meta) else None
            if res is not None:
                res["collections"] = explore.collections(meta, emb)
                res["stats"]["collections"] = len(res["collections"])
            self.cache = (key, res)
            return res

    def nearby(self, uuid):
        meta, embeddings = self.vectors()
        return explore.nearby(meta, embeddings, uuid)

    def search(self, query):
        if not isinstance(query, str):
            raise ValueError("Enter a phrase to search")
        query = query.strip()
        if not 2 <= len(query) <= 160:
            raise ValueError("Enter 2 to 160 characters to search")
        if not model.present():
            raise ValueError("Download the model before searching")
        if not self.activity_lock.acquire(blocking=False):
            raise ValueError("A search is already running")
        try:
            if scan.running():
                raise ValueError("Wait for the scan to finish before searching")
            meta, embeddings = self.vectors()
            if not meta:
                return {"query": query, "photos": []}
            import numpy as np
            from litert_lm import Backend, Content, EmbeddingEngine
            with EmbeddingEngine(MODEL_FILE, backend=Backend.GPU()) as engine:
                response = engine.compute_embedding(Content.Text("task: search result | query: " + query))
            vector = np.asarray(response.embedding, dtype=np.float32)
            return {"query": query, "photos": explore.nearest(meta, embeddings, vector)}
        finally:
            self.activity_lock.release()

    def known(self, uuids):
        con = store.connect()
        have = {r[0] for r in con.execute("SELECT uuid FROM photos")}
        return all(u in have for u in uuids)

    def library_access(self):
        """Check the same library database the scanner reads, without starting a scan."""
        if scan.state["phase"] in ("embedding", "done"):
            return {"state": "ready"}
        try:
            from osxphotos.utils import get_last_library_path
            library = get_last_library_path()
            if not library:
                return {"state": "unknown"}
            path = Path(library)
            if path.is_dir():
                path = path / "database" / "Photos.sqlite"
                if not path.exists():
                    path = path.with_name("photos.db")
            with path.open("rb") as database:
                database.read(16)
            return {"state": "ready"}
        except PermissionError:
            return {"state": "blocked"}
        except (OSError, ValueError):
            return {"state": "unknown"}

    def system_specs(self):
        """Report local compatibility separately from performance guidance."""
        macos = platform.mac_ver()[0]
        try:
            version = tuple(int(part) for part in macos.split(".")[:2])
        except ValueError:
            version = ()
        try:
            memory = int(subprocess.check_output(
                ["/usr/sbin/sysctl", "-n", "hw.memsize"], text=True,
                stderr=subprocess.DEVNULL, timeout=2).strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            memory = None
        try:
            free = shutil.disk_usage(APP_DIR).free
        except OSError:
            free = None
        arch = platform.machine()
        return {
            "architecture": arch,
            "macos": macos,
            "memory_bytes": memory,
            "free_bytes": free,
            "required_ok": arch == "arm64" and version >= (13, 0),
            "model_download_bytes": model.SIZE_HINT,
        }


def make_handler(app):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _ok_host(self):
            return self.headers.get("Host", "") in (f"127.0.0.1:{app.port}", f"localhost:{app.port}")

        def _json(self, obj, code=200):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def _deny(self):
            self._json({"error": "forbidden"}, 403)

        def _authed(self, q):
            tok = self.headers.get("X-Tidy-Token") or (q.get("t") or [""])[0]
            return secrets.compare_digest(tok, app.token)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if not self._ok_host() or not self._authed(q):
                return self._deny()
            if u.path == "/":
                b = open(STATIC, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; img-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
                self.end_headers()
                self.wfile.write(b)
            elif u.path == "/api/status":
                self._json({**scan.state, "dry_run": app.dry_run, "model": model.status()})
            elif u.path == "/api/access":
                self._json({"library": app.library_access()})
            elif u.path == "/api/specs":
                self._json(app.system_specs())
            elif u.path == "/api/results":
                sim = float((q.get("sim") or [groups.SIM_DEFAULT])[0])
                self._json(app.results(min(max(sim, 0.85), 0.99)) or {"empty": True})
            elif u.path == "/api/nearby":
                uuid = (q.get("uuid") or [""])[0]
                if not UUID_RE.fullmatch(uuid):
                    return self._json({"error": "invalid photo id"}, 400)
                try:
                    self._json(app.nearby(uuid))
                except ValueError as error:
                    self._json({"error": str(error)}, 400)
            elif u.path.startswith("/thumb/"):
                uuid = u.path[len("/thumb/"):-4]
                f = os.path.join(THUMBS, uuid + ".jpg")
                if not UUID_RE.match(uuid) or not os.path.exists(f):
                    return self._json({"error": "not found"}, 404)
                b = open(f, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                self.wfile.write(b)
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            if not self._ok_host() or not self._authed({}):
                return self._deny()
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            if u.path == "/api/scan":
                if not model.present():
                    return self._json({"error": "The AI model has not been downloaded yet"}, 400)
                with app.activity_lock:
                    self._json({"started": scan.start(app.limit)})
            elif u.path == "/api/model/download":
                self._json({"started": model.start()})
            elif u.path == "/api/search":
                try:
                    self._json(app.search(body.get("query", "") if isinstance(body, dict) else ""))
                except (ValueError, RuntimeError) as error:
                    self._json({"error": str(error)}, 400)
            elif u.path == "/api/send":
                uuids = body.get("uuids") or []
                try:
                    if not app.known(uuids):
                        raise ValueError("unknown photo id")
                    self._json(send.make_review_album(uuids, app.dry_run))
                except Exception as e:
                    self._json({"error": str(e)}, 400)
            else:
                self._json({"error": "not found"}, 404)
    return H


def serve(port=8765, dry_run=False, limit=None):
    app = App(port, dry_run, limit)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    app.port = srv.server_address[1]
    url = f"http://127.0.0.1:{app.port}/?t={app.token}"
    return srv, url
