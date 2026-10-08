"""One-time download of the open embedding model. This is the only network access in the whole app."""
import hashlib, os, threading, urllib.error, urllib.request
from .paths import MODEL_FILE, MODEL_REPO

URL = os.environ.get("PHOTOTIDY_MODEL_URL") or \
    f"https://huggingface.co/{MODEL_REPO}/resolve/main/embeddinggemma-2-740m.litertlm"
SIZE_HINT = 484622336

state = {"phase": "ready" if os.path.exists(MODEL_FILE) else "missing", "done": 0, "total": SIZE_HINT, "error": None}
_lock = threading.Lock()


def present():
    return os.path.exists(MODEL_FILE)


def status():
    if present() and state["phase"] != "downloading":
        state.update(phase="ready", error=None)
    return dict(state)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _expected():
    """sha256 + size published by Hugging Face for the file (empty if unavailable, e.g. a test mirror)."""
    try:
        urllib.request.build_opener(_NoRedirect).open(urllib.request.Request(URL, method="HEAD"), timeout=30)
    except urllib.error.HTTPError as e:
        etag = (e.headers.get("X-Linked-ETag") or "").strip('"')
        size = int(e.headers.get("X-Linked-Size") or 0)
        return (etag if len(etag) == 64 else ""), size
    return "", 0


def _download():
    part = MODEL_FILE + ".part"
    try:
        state.update(phase="downloading", done=0, error=None)
        want_sha, want_size = _expected()
        total = want_size or SIZE_HINT
        state["total"] = total
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if have > total:
            os.remove(part)
            have = 0
        if have < total:
            req = urllib.request.Request(URL, headers={"User-Agent": "PhotoTidy", **({"Range": f"bytes={have}-"} if have else {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:
                    have = 0
                with open(part, "ab" if have else "wb") as f:
                    state["done"] = have
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        state["done"] += len(chunk)
        if want_size and os.path.getsize(part) != want_size:
            raise RuntimeError("download was incomplete; press the button again to resume")
        if want_sha:
            h = hashlib.sha256()
            with open(part, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    h.update(b)
            if h.hexdigest() != want_sha:
                os.remove(part)
                raise RuntimeError("downloaded file failed its integrity check and was discarded; please try again")
        os.replace(part, MODEL_FILE)
        state.update(phase="ready", error=None)
    except Exception as e:
        state.update(phase="missing", error=f"{type(e).__name__}: {e}")
    finally:
        _lock.release()


def start():
    if present() or not _lock.acquire(blocking=False):
        return False
    threading.Thread(target=_download, daemon=True).start()
    return True
