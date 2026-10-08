# Photo Tidy

Find near-duplicate photos, screenshots and blurry shots in your Mac's Photos library, and clean them up safely.
**100% local.** Photos are analysed on your Mac with a small open AI model. Nothing is uploaded, ever.

- **Similar photos**: groups bursts and near-identical shots, keeps the best one (favorites and edited photos win), and only suggests removing photos that are almost identical to the keeper.
- **Screenshots** and **blurry photos** are listed separately and are never pre-selected.
- **Explore**: search your indexed photos with a phrase, or click the magnifier on a photo to find visual matches. Matching runs locally with the same EmbeddingGemma 2 model; search results are ranked similarities, not exact labels.
- **Collections**: browse virtual events grouped by capture time, with visually related scenes inside each event. These are rebuilt from the local index and do not create Photos albums.
- **Safe by design**: Photo Tidy never deletes or edits anything. You choose photos, it creates a new **"Tidy Review"** album in Photos, and you delete from there. Photos keeps deleted items in *Recently Deleted* for 30 days.

## Install

1. Download `PhotoTidy-x.y.z.dmg` from the [Releases](../../releases) page and drag **Photo Tidy** to Applications.
2. The current build is **not signed or notarized by Apple**, so macOS may block the first launch. Try opening the app once, then go to *System Settings > Privacy & Security > Open Anyway*. Only open software you downloaded from a source you trust.
3. The welcome screen shows how scanning, review, and album creation work. Use **Check this Mac** for a local compatibility check, then **Check access** to see whether Photo Tidy can read your library. If macOS blocks it, enable Photo Tidy in *System Settings > Privacy & Security > Full Disk Access*, then reopen the app.
4. Open the library. On first use, click **Download Model** to get [EmbeddingGemma 2](https://huggingface.co/litert-community/embeddinggemma-2-740m-litert-lm) (485 MB, once, checksum-verified). This is the app's only network download; photos stay on your Mac.
5. Click **Scan Library**. macOS may ask to let Photo Tidy access Photos data. Then use **Explore** for phrase search, a photo's magnifier for similar images, or **Collections** for local scene and event groups. Photos album permission is requested later, only when you create a review album.

Requires an **Apple Silicon** Mac (M1 or newer) on **macOS 13 or later**. Allow about **485 MB** for the one-time model download and additional space for thumbnails and the analysis cache, which grows with library size. **8 GB RAM** and **2 GB free storage** are practical suggestions, not tested hard minimums. The bundled app itself is about **220 MB**. The preflight button checks the Mac locally and distinguishes requirements from suggestions. Works with the system Photos library, including iCloud Photos libraries with "Optimize Mac Storage" (it uses the previews already on your Mac).

## How it works

| Piece | What it does |
|---|---|
| `photo_tidy/` (Python) | Reads the Photos database read-only with [osxphotos](https://github.com/RhetTbull/osxphotos), embeds each photo with [EmbeddingGemma 2](https://huggingface.co/litert-community/embeddinggemma-2-740m-litert-lm) via LiteRT-LM on the Mac's GPU, groups similar photos, and serves the UI on `127.0.0.1` only. |
| `app/main.swift` | Native window (WebKit), starts the bundled Python engine, and creates the review album with PhotoKit. |
| Cache | `~/Library/Application Support/PhotoTidy/` holds the model, analysis cache and small thumbnails of your photos. Delete the folder to remove everything (menu: *Photo Tidy > Show Data Folder*). |

Safety details: the local server binds to `127.0.0.1` with a random per-launch token and a Host-header check; the page loads no external assets (strict CSP); the window refuses to navigate anywhere but its own localhost page.

A photo is pre-marked for removal only when it is at least 0.95 cosine-similar to the best shot of its group. The *Strictness* menu lets you loosen that (0.92 / 0.89). Review before you delete: it is a similarity model, not a mind reader.

Phrase search uses the model's text encoder against the existing 768-dimensional photo embeddings. A collection starts a new event after a six-hour capture gap, then groups visually related photos within that event. Events need at least three indexed, non-screenshot photos to appear. Search and collections work offline after the one-time model download and scan.

## Build from source

```
brew install uv                  # one-time
./scripts/build_app.sh           # -> dist/Photo Tidy.app (own Python, native window, ad-hoc signed)
./scripts/build_dmg.sh           # -> dist/PhotoTidy-<version>.dmg + .sha256
```

Needs the Xcode Command Line Tools (`xcode-select --install`). To sign with your own Developer ID and notarize (needs an Apple Developer account):

```
SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" ./scripts/build_app.sh
NOTARY_PROFILE=my-notary-profile ./scripts/build_dmg.sh
```

See [the distribution guide](docs/DISTRIBUTION.md) for certificate setup, verification, and hosting the direct download on BuildTube.

Run from source without building: `uv venv && uv pip install -r requirements.txt && .venv/bin/python -m photo_tidy` (opens your browser; add `--dry-run` to never touch Photos).

## Known limitations

- Videos, Live Photo motion and shared-album photos are not analysed.
- Ad-hoc signed builds lose their macOS permissions when you update to a new version; macOS will ask again.
- Only the system Photos library is scanned.

## License

MIT for Photo Tidy's code. Third-party: EmbeddingGemma 2 (Apache-2.0, downloaded from its publisher, not redistributed here), LiteRT-LM (Apache-2.0), osxphotos (MIT), NumPy (BSD), Pillow (HPND), Python (PSF).
