import sqlite3
import numpy as np
from .paths import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
  uuid TEXT PRIMARY KEY, ts REAL, screenshot INT, favorite INT, edited INT,
  width INT, height INT, size INT, deriv TEXT, deriv_mtime REAL,
  blur REAL, emb BLOB
);
"""


def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute(SCHEMA)
    return con


def load_embedded(con):
    rows = con.execute(
        "SELECT uuid, ts, screenshot, favorite, edited, width, height, size, blur, emb "
        "FROM photos WHERE emb IS NOT NULL ORDER BY ts"
    ).fetchall()
    meta = [dict(uuid=r[0], ts=r[1], screenshot=bool(r[2]), favorite=bool(r[3]), edited=bool(r[4]),
                 width=r[5], height=r[6], size=r[7], blur=r[8]) for r in rows]
    if not rows:
        return meta, np.zeros((0, 768), dtype=np.float32)
    emb = np.stack([np.frombuffer(r[9], dtype=np.float32) for r in rows])
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
    return meta, emb
