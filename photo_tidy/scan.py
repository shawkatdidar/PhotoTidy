import os, threading, time, traceback
import numpy as np
from PIL import Image, ImageOps
from .paths import THUMBS, MODEL_FILE
from . import store

state = {"phase": "idle", "done": 0, "total": 0, "message": "", "error": None, "started": 0.0}
_lock = threading.Lock()


def running():
    return state["phase"] in ("reading", "embedding")


def thumb_path(uuid):
    return os.path.join(THUMBS, uuid + ".jpg")


def best_derivative(p):
    cands = [x for x in (p.path_derivatives or []) if os.path.exists(x)]
    return max(cands, key=os.path.getsize) if cands else None


def sharpness(img):
    g = img.convert("L")
    g.thumbnail((512, 512))
    a = np.asarray(g, dtype=np.float32)
    lap = -4 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    return float(lap.var())


def prepare(deriv, uuid):
    img = ImageOps.exif_transpose(Image.open(deriv)).convert("RGB")
    img.thumbnail((768, 768))
    img.save(thumb_path(uuid), quality=85)
    return sharpness(img)


def run(limit=None):
    if not _lock.acquire(blocking=False):
        return
    try:
        state.update(phase="reading", done=0, total=0, message="Reading your Photos library (read-only). If macOS asks to let Photo Tidy access data from other apps, choose Allow.",
                     error=None, started=time.time())
        import osxphotos
        from litert_lm import Backend, Content, EmbeddingEngine

        if not os.path.exists(MODEL_FILE):
            raise RuntimeError("The AI model has not been downloaded yet.")
        con = store.connect()
        try:
            db = osxphotos.PhotosDB()
        except PermissionError as e:
            raise RuntimeError("macOS is blocking access to your Photos library. Open System Settings > Privacy & Security > "
                               "Full Disk Access, switch on Photo Tidy, then quit and reopen the app.") from e
        photos = [p for p in db.photos() if p.isphoto and not p.hidden]
        if limit:
            photos = photos[:limit]
        todo = []
        for p in photos:
            d = best_derivative(p)
            if not d:
                continue
            mt = os.path.getmtime(d)
            row = con.execute("SELECT deriv, deriv_mtime, emb FROM photos WHERE uuid=?", (p.uuid,)).fetchone()
            meta = (p.date.timestamp() if p.date else 0.0, int(p.screenshot), int(p.favorite),
                    int(p.hasadjustments), p.width or 0, p.height or 0, p.original_filesize or 0)
            if row is None:
                con.execute("INSERT INTO photos (uuid, ts, screenshot, favorite, edited, width, height, size, deriv, deriv_mtime)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?)", (p.uuid, *meta, d, mt))
            else:
                con.execute("UPDATE photos SET ts=?, screenshot=?, favorite=?, edited=?, width=?, height=?, size=?,"
                            " deriv=?, deriv_mtime=? WHERE uuid=?", (*meta, d, mt, p.uuid))
            if row is None or row[2] is None or row[0] != d or row[1] != mt:
                todo.append((p.uuid, d))
        con.commit()

        state.update(phase="embedding", total=len(todo), done=0,
                     message=f"Analysing {len(todo)} new photos on this Mac…")
        if todo:
            gpu = Backend.GPU()
            with EmbeddingEngine(MODEL_FILE, backend=gpu, vision_backend=gpu) as eng:
                for i, (uuid, d) in enumerate(todo, 1):
                    try:
                        blur = prepare(d, uuid)
                        r = eng.compute_embedding(Content.ImageFile(thumb_path(uuid)))
                        emb = np.array(r.embedding, dtype=np.float32)
                        con.execute("UPDATE photos SET blur=?, emb=? WHERE uuid=?", (blur, emb.tobytes(), uuid))
                    except Exception:
                        traceback.print_exc()
                    state["done"] = i
                    if i % 25 == 0:
                        con.commit()
        con.commit()
        state.update(phase="done", message="Scan complete.")
    except Exception as e:
        traceback.print_exc()
        state.update(phase="error", error=f"{type(e).__name__}: {e}", message="Scan failed.")
    finally:
        _lock.release()


def start(limit=None):
    if running() or _lock.locked():
        return False
    state.update(phase="reading", done=0, total=0, message="Preparing your library scan…",
                 error=None, started=time.time())
    threading.Thread(target=run, args=(limit,), daemon=True).start()
    return True
