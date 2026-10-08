<p align="center">
  <img src="docs/assets/app-icon.png" alt="Photo Tidy app icon" width="88">
</p>

<h1 align="center">Photo Tidy</h1>

<p align="center">
  Find the photos that matter. Clear the clutter.<br>
  A private photo companion for Mac.
</p>

<p align="center">
  <a href="https://github.com/shawkatdidar/PhotoTidy/releases/download/v1.1.0/PhotoTidy-1.1.0.dmg"><strong>Download for Mac</strong></a>
  &nbsp;·&nbsp; <a href="https://buildtube.app/PhotoTidy/">Explore the website</a>
  &nbsp;·&nbsp; <a href="https://buymeacoffee.com/shawkatm_1776">Support the project</a>
</p>

<p align="center"><sub>Free and open source · Apple Silicon · macOS 13 or later</sub></p>

![Three printed photos on a light tabletop](docs/assets/readme-hero.png)

Photo Tidy finds similar shots, screenshots, and blurry photos in your Mac's Photos library. **Your photos stay on your Mac.** The model runs locally; the app does not upload your library. Once the model has downloaded, you can even turn off Wi-Fi and keep using it.

## A calmer way to clean up

| Find | Explore | Review |
| :--- | :--- | :--- |
| See near-duplicate groups, screenshots, and blurry shots. | Search with a phrase, find visual matches, and browse local event collections. | Choose what to keep. Send selected photos to a **Tidy Review** album in Photos. |

Photo Tidy never deletes or edits your photos. You make the final decision in Apple Photos. Screenshots and blurry photos are never preselected.

## How it works

```text
Your Photos library       Local AI model          You decide
       ◇                       ◇                     ◇
Read existing previews  →  Find related photos  →  Review in Photos
```

The app reads your system Photos library, makes a local index, and uses [EmbeddingGemma 2](https://huggingface.co/litert-community/embeddinggemma-2-740m-litert-lm) through LiteRT-LM to compare photos. The model is a **485 MB one-time download** from its publisher. Your photos and search stay local. The app's cache, model, and small thumbnails live in `~/Library/Application Support/PhotoTidy/`.

## Get started

1. **Download** the [latest Mac disk image](https://github.com/shawkatdidar/PhotoTidy/releases/download/v1.1.0/PhotoTidy-1.1.0.dmg), open it, and drag **Photo Tidy** to Applications.
2. **Open the app.** This build is not Apple notarized. If macOS blocks it, try opening it once, then choose **System Settings → Privacy & Security → Open Anyway**. Only open software from a source you trust.
3. **Check your Mac and access.** The welcome screen has **Check this Mac** and **Check access** buttons. If Photos access is blocked, grant **Full Disk Access** in System Settings and reopen the app.
4. **Download the model** when prompted, then **Scan Library**. macOS may request access to Photos data. Album permission is requested later, when you create a review album.
5. **Explore and review.** Search by phrase, tap a photo's magnifier for visual matches, or browse Collections. Add photos you choose to the Tidy Review album.

| Mac requirement | Details |
| :--- | :--- |
| System | Apple Silicon (M1 or newer), macOS 13 or later |
| Practical recommendation | 8 GB RAM and 2 GB free storage; the cache grows with your library |
| Library | Your system Photos library, including iCloud Photos with *Optimize Mac Storage* using previews already on the Mac |

The in-app check separates requirements from recommendations. The app itself is about 220 MB, plus the model download and cache.

## Build from source

Install the Xcode Command Line Tools and [uv](https://docs.astral.sh/uv/), then run:

```sh
xcode-select --install
brew install uv
./scripts/build_app.sh
./scripts/build_dmg.sh
```

The scripts produce `dist/Photo Tidy.app` and a disk image in `dist/`. To run the Python engine directly:

```sh
uv venv
uv pip install -r requirements.txt
.venv/bin/python -m photo_tidy --dry-run
```

For Developer ID signing, notarization, and release verification, see the [distribution guide](docs/DISTRIBUTION.md).

<details>
<summary><strong>Technical and safety details</strong></summary>

- The Python engine reads Photos through [osxphotos](https://github.com/RhetTbull/osxphotos) and serves the UI only on `127.0.0.1`. The native Swift window handles PhotoKit album creation.
- The local server uses a random token for each launch and checks the Host header. The page loads no external assets, and the app window stays on its own local page.
- Only very close matches are premarked for review (0.95 cosine similarity by default). You can adjust strictness in the app; always review the suggestions.
- Search compares the model's text output with the local photo index. Collections group photos by capture time and visual similarity; they do not create Photos albums.
- Videos, Live Photo motion, and shared-album photos are not analyzed. Only the system Photos library is scanned.
- This release is ad-hoc signed. macOS may ask for permissions again after an update.

</details>

## License

Photo Tidy's code is [MIT licensed](LICENSE). The separately downloaded EmbeddingGemma 2 model and LiteRT-LM are Apache-2.0; osxphotos is MIT, NumPy is BSD, Pillow is HPND, and Python uses the PSF license.
