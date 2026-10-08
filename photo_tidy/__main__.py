import argparse, os, subprocess, threading, time
from .server import serve

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--dry-run", action="store_true", help="never touch Photos; just log what would be sent")
ap.add_argument("--no-open", action="store_true")
ap.add_argument("--exit-with-parent", action="store_true", help="quit when the launching app exits")
ap.add_argument("--limit", type=int, default=None, help="scan only the first N photos (testing)")
a = ap.parse_args()
srv, url = serve(a.port, a.dry_run, a.limit)
print("Photo Tidy is running locally at", url, flush=True)
if not a.no_open:
    subprocess.run(["open", url])
if a.exit_with_parent:
    parent = os.getppid()

    def watch():
        while os.getppid() == parent:
            time.sleep(1)
        os._exit(0)
    threading.Thread(target=watch, daemon=True).start()
try:
    srv.serve_forever()
except KeyboardInterrupt:
    pass
