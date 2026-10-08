import os

APP_DIR = os.environ.get("PHOTOTIDY_HOME") or os.path.expanduser("~/Library/Application Support/PhotoTidy")
DB_PATH = os.path.join(APP_DIR, "cache.db")
THUMBS = os.path.join(APP_DIR, "thumbs")
MODEL_DIR = os.path.join(APP_DIR, "model")
MODEL_FILE = os.path.join(MODEL_DIR, "embeddinggemma-2-740m.litertlm")
MODEL_REPO = "litert-community/embeddinggemma-2-740m-litert-lm"

for d in (APP_DIR, THUMBS, MODEL_DIR):
    os.makedirs(d, exist_ok=True)
