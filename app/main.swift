import Cocoa
import WebKit
import Photos

// Photo Tidy host: shows the local web UI in a window, runs the bundled Python server on 127.0.0.1,
// and creates the review album through PhotoKit. It never deletes or edits photos.

let uuidRegex = try! NSRegularExpression(pattern: "^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$")
let logURL = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/PhotoTidy.log")
let dataDir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/PhotoTidy")

final class Host: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate, NSWindowDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var proc: Process?
    var quitting = false
    let args = CommandLine.arguments

    func applicationDidFinishLaunching(_ n: Notification) {
        buildMenu()
        buildWindow()
        startServer()
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ n: Notification) {
        quitting = true
        proc?.terminate()
    }

    // MARK: window

    func buildWindow() {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .nonPersistent()
        cfg.userContentController.add(self, name: "tidy")
        web = WKWebView(frame: .zero, configuration: cfg)
        web.appearance = NSAppearance(named: .aqua)
        web.navigationDelegate = self
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1180, height: 820),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered, defer: false)
        window.title = "Photo Tidy"
        window.appearance = NSAppearance(named: .aqua)
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.minSize = NSSize(width: 760, height: 560)
        window.contentView = web
        window.delegate = self
        window.setFrameAutosaveName("PhotoTidyMain")
        if !window.setFrameUsingName("PhotoTidyMain") { window.center() }
        window.makeKeyAndOrderFront(nil)
        showMessage("Starting…", "Photo Tidy is starting its local engine.")
    }

    func showMessage(_ title: String, _ body: String) {
        let esc = { (s: String) in s.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;") }
        web.loadHTMLString("""
        <html><body style="font:16px -apple-system;display:flex;height:100vh;margin:0;align-items:center;justify-content:center;color:#6e6e73">
        <div style="max-width:520px;text-align:center"><h2 style="color:#1d1d1f">\(esc(title))</h2><p>\(esc(body))</p></div></body></html>
        """, baseURL: nil)
    }

    // MARK: python server

    func startServer() {
        let res = Bundle.main.resourceURL!
        var py = res.appendingPathComponent("python/bin/python3")
        if !FileManager.default.fileExists(atPath: py.path) { py = res.appendingPathComponent("python/bin/python3.12") }
        let appCode = res.appendingPathComponent("app")
        let devCode = URL(fileURLWithPath: args.first { $0.hasPrefix("--dev-code=") }.map { String($0.dropFirst(11)) } ?? "")
        let p = Process()
        p.executableURL = py
        var pargs = ["-m", "photo_tidy", "--port", "0", "--no-open", "--exit-with-parent"]
        if args.contains("--dry-run") { pargs.append("--dry-run") }
        if let i = args.firstIndex(of: "--limit"), i + 1 < args.count { pargs += ["--limit", args[i + 1]] }
        p.arguments = pargs
        var env = ["PYTHONPATH": appCode.path, "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                   "HOME": NSHomeDirectory(), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"]
        for k in ["PHOTOTIDY_HOME", "PHOTOTIDY_MODEL_URL"] { if let v = ProcessInfo.processInfo.environment[k] { env[k] = v } }
        if args.contains(where: { $0.hasPrefix("--dev-code=") }) { env["PYTHONPATH"] = devCode.path }
        p.environment = env

        FileManager.default.createFile(atPath: logURL.path, contents: nil, attributes: nil)
        let log = try? FileHandle(forWritingTo: logURL)
        log?.seekToEndOfFile()
        p.standardError = log ?? FileHandle.nullDevice
        let out = Pipe()
        p.standardOutput = out
        var buffer = ""
        out.fileHandleForReading.readabilityHandler = { [weak self] h in
            let d = h.availableData
            if d.isEmpty { return }
            buffer += String(decoding: d, as: UTF8.self)
            guard let r = buffer.range(of: "running locally at ") else { return }
            let rest = buffer[r.upperBound...]
            guard let nl = rest.firstIndex(of: "\n"), let url = URL(string: String(rest[..<nl])) else { return }
            buffer = ""
            h.readabilityHandler = nil
            if self?.args.contains("--debug-url") == true { log?.write(Data("DEBUG-URL \(url.absoluteString)\n".utf8)) }
            DispatchQueue.main.async {
                guard let self = self else { return }
                var page = URLComponents(url: url, resolvingAgainstBaseURL: false)!
                if UserDefaults.standard.bool(forKey: "hasCompletedOnboarding") {
                    page.queryItems?.append(URLQueryItem(name: "onboarded", value: "1"))
                }
                self.web.load(URLRequest(url: page.url!))
            }
        }
        p.terminationHandler = { [weak self] pr in
            guard let self = self, !self.quitting else { return }
            DispatchQueue.main.async {
                self.showMessage("Photo Tidy's engine stopped",
                                 "It exited with code \(pr.terminationStatus). Details are in ~/Library/Logs/PhotoTidy.log. Quit and reopen the app to try again.")
            }
        }
        do { try p.run(); proc = p } catch {
            showMessage("Could not start", "\(error.localizedDescription)")
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 40) { [weak self] in
            if self?.web.url == nil || self?.web.url?.scheme == "about" {
                self?.showMessage("Taking too long to start", "Details are in ~/Library/Logs/PhotoTidy.log.")
            }
        }
    }

    // Only ever show our own localhost page.
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        let u = a.request.url
        decisionHandler(u?.scheme == "about" || u?.host == "127.0.0.1" ? .allow : .cancel)
    }

    // MARK: PhotoKit bridge (create a NEW review album; nothing is deleted or edited)

    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        guard m.frameInfo.isMainFrame, m.frameInfo.request.url?.host == "127.0.0.1",
              let body = m.body as? [String: Any], let action = body["action"] as? String
        else { return reply(["error": "invalid request"]) }
        if action == "completeOnboarding" {
            UserDefaults.standard.set(true, forKey: "hasCompletedOnboarding")
            return
        }
        if action == "getPermissions" {
            let status = PHPhotoLibrary.authorizationStatus(for: .readWrite)
            let value: String
            switch status {
            case .authorized: value = "ready"
            case .limited: value = "limited"
            case .denied, .restricted: value = "blocked"
            default: value = "notAsked"
            }
            replyPermissions(["photos": value])
            return
        }
        guard action == "createAlbum",
              let uuids = body["uuids"] as? [String], !uuids.isEmpty, uuids.count <= 50_000,
              uuids.allSatisfy({ uuidRegex.firstMatch(in: $0, range: NSRange($0.startIndex..., in: $0)) != nil })
        else { return reply(["error": "invalid request"]) }
        let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd HH:mm"
        let name = "Tidy Review " + df.string(from: Date())
        PHPhotoLibrary.requestAuthorization(for: .readWrite) { status in
            guard status == .authorized || status == .limited else {
                return self.reply(["error": "Photo Tidy does not have access to Photos. Open System Settings > Privacy & Security > Photos, allow Photo Tidy, then try again."])
            }
            let ids = uuids.map { $0.uppercased() + "/L0/001" }
            let assets = PHAsset.fetchAssets(withLocalIdentifiers: ids, options: nil)
            if assets.count == 0 { return self.reply(["error": "None of those photos could be found in Photos."]) }
            PHPhotoLibrary.shared().performChanges({
                let req = PHAssetCollectionChangeRequest.creationRequestForAssetCollection(withTitle: name)
                req.addAssets(assets)
            }) { ok, err in
                if ok { self.reply(["album": name, "requested": uuids.count, "added": assets.count, "dry_run": false]) }
                else { self.reply(["error": err?.localizedDescription ?? "Photos could not create the album."]) }
            }
        }
    }

    func reply(_ obj: [String: Any]) {
        guard let d = try? JSONSerialization.data(withJSONObject: obj), let s = String(data: d, encoding: .utf8) else { return }
        DispatchQueue.main.async { self.web.evaluateJavaScript("window.__album && window.__album(\(s))", completionHandler: nil) }
    }

    func replyPermissions(_ obj: [String: Any]) {
        guard let d = try? JSONSerialization.data(withJSONObject: obj), let s = String(data: d, encoding: .utf8) else { return }
        DispatchQueue.main.async { self.web.evaluateJavaScript("window.__permissions && window.__permissions(\(s))", completionHandler: nil) }
    }

    // MARK: menus

    @objc func showDataFolder() {
        try? FileManager.default.createDirectory(at: dataDir, withIntermediateDirectories: true)
        NSWorkspace.shared.open(dataDir)
    }

    @objc func showLog() { NSWorkspace.shared.open(logURL) }

    func buildMenu() {
        let main = NSMenu()
        func item(_ menu: NSMenu, _ title: String, _ sel: Selector?, _ key: String = "", target: AnyObject? = nil) {
            let i = NSMenuItem(title: title, action: sel, keyEquivalent: key)
            i.target = target
            menu.addItem(i)
        }
        let appItem = NSMenuItem(); main.addItem(appItem)
        let appMenu = NSMenu(); appItem.submenu = appMenu
        item(appMenu, "About Photo Tidy", #selector(NSApplication.orderFrontStandardAboutPanel(_:)))
        appMenu.addItem(.separator())
        item(appMenu, "Show Data Folder (cache and thumbnails)", #selector(showDataFolder), target: self)
        item(appMenu, "Show Log", #selector(showLog), target: self)
        appMenu.addItem(.separator())
        item(appMenu, "Hide Photo Tidy", #selector(NSApplication.hide(_:)), "h")
        appMenu.addItem(.separator())
        item(appMenu, "Quit Photo Tidy", #selector(NSApplication.terminate(_:)), "q")

        let editItem = NSMenuItem(); main.addItem(editItem)
        let edit = NSMenu(title: "Edit"); editItem.submenu = edit
        item(edit, "Copy", #selector(NSText.copy(_:)), "c")
        item(edit, "Paste", #selector(NSText.paste(_:)), "v")
        item(edit, "Select All", #selector(NSText.selectAll(_:)), "a")

        let winItem = NSMenuItem(); main.addItem(winItem)
        let win = NSMenu(title: "Window"); winItem.submenu = win
        item(win, "Minimize", #selector(NSWindow.performMiniaturize(_:)), "m")
        item(win, "Zoom", #selector(NSWindow.performZoom(_:)))
        NSApp.windowsMenu = win
        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let host = Host()
app.delegate = host
app.setActivationPolicy(.regular)
app.run()
