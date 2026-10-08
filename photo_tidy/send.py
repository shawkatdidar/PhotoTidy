import re, subprocess, time

UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$")


def make_review_album(uuids, dry_run=False):
    """Adds the given photos to a NEW album in Photos. Never deletes or edits anything."""
    if not uuids or not all(UUID_RE.match(u) for u in uuids):
        raise ValueError("invalid photo ids")
    name = "Tidy Review " + time.strftime("%Y-%m-%d %H:%M")
    ids = ", ".join('"%s/L0/001"' % u.upper() for u in uuids)
    script = f'''
tell application "Photos"
  set theAlbum to make new album named "{name}"
  set theItems to {{}}
  repeat with theId in {{{ids}}}
    try
      set end of theItems to (media item id (theId as text))
    end try
  end repeat
  if (count of theItems) > 0 then add theItems to theAlbum
  return (count of theItems) as text
end tell'''
    if dry_run:
        print(f"[dry-run] would create album {name!r} with {len(uuids)} photos")
        return {"album": name, "requested": len(uuids), "added": len(uuids), "dry_run": True}
    try:
        r = subprocess.run(["osascript", "-"], input=script, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Photos did not respond. Look for a macOS prompt asking to let this app control Photos "
                           "(System Settings > Privacy & Security > Automation), allow it, and try again.")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "osascript failed")
    return {"album": name, "requested": len(uuids), "added": int(r.stdout.strip() or 0), "dry_run": False}
