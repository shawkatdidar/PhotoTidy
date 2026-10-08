# Photo Tidy release: signing, notarization, and download

Photo Tidy is a direct-download macOS app. The website can live at
`https://buildtube.app/PhotoTidy/`. The DMG is larger than Cloudflare Pages'
single-file limit. A GitHub Release is a practical free starting point for the
DMG, with the public source code in the same repository. Later, an R2 bucket on
`https://downloads.buildtube.app/` can give the file a branded download host.

## Free public release on GitHub

1. Create a public Photo Tidy repository containing the source, MIT license,
   README, requirements, and build scripts. Keep `.venv/`, `dist/`, `site/`,
   generated caches, and personal photo data out of Git. The model downloads
   separately on first use and should not be committed to the repository.
2. Create a `v1.1.0` GitHub Release and attach the tested
   `dist/PhotoTidy-1.1.0.dmg` and its `.sha256` file as release assets. Do not
   commit the DMG to Git history. GitHub accepts release assets under 2 GiB.
3. Verify the release asset downloads and matches the local SHA-256. In
   BuildTube's `site-src/site.config.json`, set `photoTidyDownloadUrl` to the
   direct asset URL (for example,
   `https://github.com/OWNER/REPO/releases/download/v1.1.0/PhotoTidy-1.1.0.dmg`).
   Keep `photoTidyNotarized` set to `false`, then rebuild and check the page.

Publishing source and a checksum lets people inspect or build the app and
check the download. It does not make an unsigned app notarized or remove the
macOS first-open warning. Use Apple's **Open Anyway** path for the current
unsigned build; do not ask users to disable Gatekeeper system-wide.

The steps below are optional until you decide the smoother signed first launch
is worth Apple Developer Program membership.

## One-time Apple setup

1. Join the Apple Developer Program and create a **Developer ID Application**
   certificate for direct distribution. Download and install it into the Mac's
   login keychain, with its private key. Apple requires the Account Holder role
   to create this certificate.
2. Check that macOS can see it:

   ```sh
   security find-identity -v -p codesigning
   ```

   Look for `Developer ID Application: Your Name (TEAMID)`. The existing
   `Earshot Local Signing` identity is not a Developer ID certificate.
3. Set up a `notarytool` keychain profile. Run this interactively; it prompts
   for an Apple app-specific password, so it is not saved in shell history:

   ```sh
   xcrun notarytool store-credentials PhotoTidyNotary \
     --apple-id "YOUR_APPLE_ID" --team-id "TEAMID"
   ```

   Create the app-specific password in your Apple Account's sign-in and security
   settings. Do not put the password or a `.p12` private key in the repository.

## Build and verify each release

Run from the Photo Tidy project folder on an Apple Silicon Mac:

```sh
SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" ./scripts/build_app.sh
NOTARY_PROFILE=PhotoTidyNotary ./scripts/build_dmg.sh
```

The first script signs nested binaries and the app with hardened runtime and a
secure timestamp. It stops if any nested signature fails. The second script
checks for a valid Developer ID app signature, creates the DMG, submits it to
Apple, staples the notarization ticket, validates the ticket, and writes the
SHA-256 checksum. Notarization must succeed before distributing this signed
release. If Apple rejects it, inspect the submission log with:

```sh
xcrun notarytool log SUBMISSION_ID --keychain-profile PhotoTidyNotary
```

Final local checks:

```sh
codesign --verify --deep --strict "dist/Photo Tidy.app"
spctl --assess --type execute --verbose "dist/Photo Tidy.app"
xcrun stapler validate "dist/PhotoTidy-$(cat VERSION).dmg"
shasum -a 256 "dist/PhotoTidy-$(cat VERSION).dmg"
```

Keep the release page's version, SHA-256, and first-open instructions in sync
with the actual DMG. A notarized release should not tell people to bypass
Gatekeeper.

## Optional branded download host

Cloudflare Pages accepts a maximum 25 MiB per site asset. Create an R2 bucket,
attach `downloads.buildtube.app` as its public custom domain in Cloudflare,
then upload the signed and notarized DMG. Example commands after Wrangler login:

```sh
npx wrangler r2 bucket create phototidy-releases
npx wrangler r2 object put phototidy-releases/PhotoTidy-1.1.0.dmg \
  --file "dist/PhotoTidy-1.1.0.dmg" --remote \
  --content-type application/x-apple-diskimage \
  --content-disposition 'attachment; filename="PhotoTidy-1.1.0.dmg"'
```

The custom domain is connected in the R2 bucket's **Settings → Custom Domains**.
Confirm the public URL downloads the exact uploaded file and that its SHA-256
matches the local release. Only then enable the website's download buttons.

Apple guidance: [Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/),
[notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
[notarytool workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
Cloudflare guidance: [Pages limits](https://developers.cloudflare.com/pages/platform/limits/),
[R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/),
[Wrangler R2 commands](https://developers.cloudflare.com/workers/wrangler/commands/r2/).
