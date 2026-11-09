import Cocoa

struct Pair: Decodable { let up: Double; let down: Double }
struct Groups: Decodable { let proxy: Pair; let direct: Pair }
struct Sample: Decodable { let online: Bool; let speed: Groups; let total: Groups; let today: Groups; let quota: QuotaStatus }

func quantity(_ value: Double, rate: Bool = false) -> String {
    let units = ["B", "KiB", "MiB", "GiB", "TiB"]
    var n = max(0, value), i = 0
    while n >= 1024 && i < 4 { n /= 1024; i += 1 }
    let digits = i == 0 || n >= 100 ? 0 : 1
    return String(format: "%.*f", digits, n) + units[i] + (rate ? "/s" : "")
}

class OrbView: NSView {
    var sample: Sample?
    var unavailable = true
    var phase: CGFloat = 0
    var showMenu: (() -> Void)?
    var detail: (() -> Void)?
    var previewAlert: (() -> Void)?
    let uploadColor = NSColor(calibratedRed: 0.64, green: 0.25, blue: 0.08, alpha: 1)
    let downloadColor = NSColor(calibratedRed: 0.06, green: 0.32, blue: 0.67, alpha: 1)
    let ink = NSColor(calibratedWhite: 0.16, alpha: 1)
    override var acceptsFirstResponder: Bool { false }

    override init(frame: NSRect) {
        super.init(frame: frame)
        setAccessibilityElement(true)
        setAccessibilityRole(.button)
        setAccessibilityLabel("流量悬浮球")
        setAccessibilityHelp("拖动调整位置；双击打开详细面板；右键打开菜单")
        toolTip = "代理流量 · 拖动移动 · 双击详情 · 右键菜单"
    }
    required init?(coder: NSCoder) { fatalError() }
    override func hitTest(_ point: NSPoint) -> NSView? {
        let p = convert(point, from: superview)
        return hypot(p.x - bounds.midX, p.y - bounds.midY) <= 46 ? self : nil
    }
    override func mouseDown(with event: NSEvent) {
        if event.modifierFlags.contains(.option) { previewAlert?() }
        else if event.clickCount == 2 { detail?() }
        else if event.modifierFlags.contains(.control) { rightMouseDown(with: event) }
        else {
            window?.performDrag(with: event)
            if let frame = window?.frame { UserDefaults.standard.set(NSStringFromPoint(frame.origin), forKey: "orbOrigin") }
        }
    }
    override func mouseUp(with event: NSEvent) {
        guard let frame = window?.frame else { return }
        UserDefaults.standard.set(NSStringFromPoint(frame.origin), forKey: "orbOrigin")
    }
    override func rightMouseDown(with event: NSEvent) {
        showMenu?()
    }
    func text(_ string: String, y: CGFloat, size: CGFloat, color: NSColor, weight: NSFont.Weight = .medium) {
        let font = NSFont.monospacedDigitSystemFont(ofSize: size, weight: weight)
        let shadow = NSShadow()
        shadow.shadowColor = NSColor.white.withAlphaComponent(0.65)
        shadow.shadowBlurRadius = 1
        shadow.shadowOffset = .zero
        let attributes: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: color, .shadow: shadow]
        let width = (string as NSString).size(withAttributes: attributes).width
        (string as NSString).draw(at: NSPoint(x: (bounds.width - width) / 2, y: y), withAttributes: attributes)
    }
    override func draw(_ dirtyRect: NSRect) {
        let circle = NSBezierPath(ovalIn: bounds.insetBy(dx: 8, dy: 8))
        NSColor.white.withAlphaComponent(0.62).setFill(); circle.fill()
        NSGraphicsContext.saveGraphicsState(); circle.addClip()
        let speed = (sample?.speed.proxy.up ?? 0) + (sample?.speed.proxy.down ?? 0)
        let activity = min(1, log10(max(1, speed)) / 7)
        for layer in 0..<2 {
            let wave = NSBezierPath(); wave.move(to: NSPoint(x: 0, y: 0)); wave.line(to: NSPoint(x: 0, y: 23))
            for x in stride(from: CGFloat(0), through: bounds.width, by: 2) {
                let y = 23 + CGFloat(activity) * 9 + sin(x / 18 + phase + CGFloat(layer) * 2) * (3 + CGFloat(activity) * 3)
                wave.line(to: NSPoint(x: x, y: y))
            }
            wave.line(to: NSPoint(x: bounds.width, y: 0)); wave.close()
            (layer == 0 ? downloadColor : uploadColor).withAlphaComponent(layer == 0 ? 0.06 : 0.035).setFill(); wave.fill()
        }
        NSGraphicsContext.restoreGraphicsState()
        downloadColor.withAlphaComponent(0.20).setStroke(); circle.lineWidth = 0.75; circle.stroke()
        let progress = min(1, max(0, (sample?.quota.percent ?? 0) / 100))
        if progress > 0 {
            let arc = NSBezierPath()
            arc.appendArc(withCenter: NSPoint(x: bounds.midX, y: bounds.midY), radius: 46,
                          startAngle: 90, endAngle: 90 - CGFloat(progress) * 360, clockwise: true)
            let tint: NSColor = (sample?.quota.stage ?? 0) >= 95 ? .systemRed : (sample?.quota.stage ?? 0) >= 80 ? .systemOrange : downloadColor
            tint.withAlphaComponent(0.65).setStroke(); arc.lineWidth = 1.7; arc.stroke()
        }
        let online = (sample?.online ?? false) && !unavailable
        let limit = sample.map { "今日 / " + limitNumber($0.quota.limit_bytes / 1e9) + "GB" } ?? "今日流量"
        text(online ? limit : "等待连接", y: 82, size: 6.5, color: ink.withAlphaComponent(0.85))
        text(online ? "↑ " + quantity(sample!.speed.proxy.up, rate: true) : "↑ —", y: 62, size: 11.5, color: uploadColor)
        text(online ? "↓ " + quantity(sample!.speed.proxy.down, rate: true) : "↓ —", y: 44, size: 11.5, color: downloadColor)
        let today = sample?.quota.used_bytes ?? 0
        text(decimalGB(today), y: 24, size: 9, color: ink)
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var panel: NSPanel!
    var orb: OrbView!
    var status: NSStatusItem!
    var timer: Timer?
    var animation: Timer?
    var loading = false
    var lastSuccess = Date.distantPast
    var launches = 0
    var alertPanel: NSPanel?
    var menuPanel: ContextMenuPanel?
    var settingsPanel: NSPanel?
    var limitField: NSTextField?
    var limitError: NSTextField?
    let root = Paths.supportRoot
    let endpoint = URL(string: "http://127.0.0.1:\(Paths.port)/api/stats")!
    lazy var session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.connectionProxyDictionary = [:]
        config.timeoutIntervalForRequest = 2
        return URLSession(configuration: config)
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        do { try Paths.prepare() } catch {
            let alert = NSAlert(); alert.messageText = "无法创建 Traffic Orb 配置目录"
            alert.informativeText = error.localizedDescription; alert.runModal(); NSApp.terminate(nil); return
        }
        // Reopening the launcher brings the existing orb forward instead of duplicating it.
        let peers = NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier!)
        if peers.contains(where: { $0.processIdentifier != ProcessInfo.processInfo.processIdentifier }) {
            peers.first(where: { $0.processIdentifier != ProcessInfo.processInfo.processIdentifier })?.activate(options: [])
            NSApp.terminate(nil); return
        }
        NSApp.setActivationPolicy(.accessory)
        panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 108, height: 108), styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.title = "流量悬浮球"
        panel.isOpaque = false; panel.backgroundColor = .clear; panel.hasShadow = false
        panel.level = .floating; panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isReleasedWhenClosed = false
        orb = OrbView(frame: NSRect(x: 0, y: 0, width: 108, height: 108))
        orb.showMenu = { [weak self] in self?.showContextMenu() }
        orb.detail = { [weak self] in self?.openDetails() }
        orb.previewAlert = { [weak self] in self?.testAlert() }
        panel.contentView = orb
        position(reset: UserDefaults.standard.integer(forKey: "appearanceVersion") < 2)
        UserDefaults.standard.set(2, forKey: "appearanceVersion")
        panel.orderFrontRegardless()
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        status.button?.image = NSImage(systemSymbolName: "waveform.path", accessibilityDescription: "流量悬浮球")
        status.button?.toolTip = "流量悬浮球"
        status.menu = makeMenu()
        poll()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.poll() }
        animation = Timer.scheduledTimer(withTimeInterval: 1 / 15, repeats: true) { [weak self] _ in
            guard let self else { return }
            if !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion { self.orb.phase += 0.045 }
            self.orb.needsDisplay = true
        }
    }
    func applicationDidBecomeActive(_ notification: Notification) {
        if let alertPanel, alertPanel.isVisible { alertPanel.makeKeyAndOrderFront(nil) }
        else if let settingsPanel, settingsPanel.isVisible { settingsPanel.makeKeyAndOrderFront(nil) }
        else if let menuPanel, menuPanel.isVisible { menuPanel.makeKeyAndOrderFront(nil) }
        else { panel?.orderFrontRegardless() }
    }
    func applicationDidResignActive(_ notification: Notification) { closeContextMenu() }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        panel?.orderFrontRegardless(); return false
    }
    func position(reset: Bool) {
        let screen = NSScreen.main ?? NSScreen.screens[0]
        let visible = screen.visibleFrame
        var origin = NSPoint(x: visible.maxX - panel.frame.width - 8, y: visible.maxY - panel.frame.height - 8)
        if !reset, let saved = UserDefaults.standard.string(forKey: "orbOrigin") {
            let candidate = NSPointFromString(saved)
            if NSScreen.screens.contains(where: { $0.visibleFrame.contains(NSRect(origin: candidate, size: panel.frame.size)) }) { origin = candidate }
        }
        panel.setFrameOrigin(origin)
        UserDefaults.standard.set(NSStringFromPoint(origin), forKey: "orbOrigin")
    }
    func makeMenu() -> NSMenu {
        let menu = NSMenu()
        for (title, action) in [("显示 / 隐藏悬浮球", #selector(toggle)), ("回到右上角", #selector(resetPosition)), ("打开详细流量面板…", #selector(openDetails)), ("设置每日限额…", #selector(showLimitSettings))] {
            let item = NSMenuItem(title: title, action: action, keyEquivalent: ""); item.target = self; menu.addItem(item)
        }
        menu.addItem(.separator())
        let info = NSMenuItem(title: "↑ 上传  ↓ 下载 · 底部为今日代理用量", action: nil, keyEquivalent: ""); info.isEnabled = false; menu.addItem(info)
        let test = NSMenuItem(title: "测试限额提醒…", action: #selector(testAlert), keyEquivalent: ""); test.target = self; menu.addItem(test)
        menu.addItem(.separator())
        let quit = NSMenuItem(title: "退出悬浮球", action: #selector(quit), keyEquivalent: "q"); quit.target = self; menu.addItem(quit)
        return menu
    }
    @objc func closeContextMenu() { menuPanel?.orderOut(nil) }
    func showContextMenu() {
        closeContextMenu()
        let screen = panel.screen ?? NSScreen.main ?? NSScreen.screens[0]
        let frame = contextMenuFrame(anchor: panel.frame, screen: screen.visibleFrame)
        let popup = ContextMenuPanel(contentRect: frame, styleMask: [.borderless], backing: .buffered, defer: false)
        popup.title = "流量球菜单"
        popup.isReleasedWhenClosed = false; popup.hidesOnDeactivate = true
        popup.isOpaque = false; popup.backgroundColor = .clear; popup.hasShadow = true
        popup.level = .popUpMenu
        popup.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        popup.appearance = NSAppearance(named: .aqua)
        let background = NSVisualEffectView(frame: NSRect(origin: .zero, size: frame.size))
        background.material = .popover; background.state = .active; background.blendingMode = .behindWindow
        background.wantsLayer = true; background.layer?.cornerRadius = 12; background.layer?.masksToBounds = true
        let title = NSTextField(labelWithString: "流量球")
        title.font = .boldSystemFont(ofSize: 14); title.frame = NSRect(x: 18, y: 298, width: 180, height: 20)
        background.addSubview(title)
        let quota = orb.sample?.quota
        let summary = NSTextField(labelWithString: quota.map { "今日 " + decimalGB($0.used_bytes) + " / " + decimalGB($0.limit_bytes) } ?? "正在连接统计接口…")
        summary.font = .systemFont(ofSize: 11); summary.textColor = .secondaryLabelColor
        summary.frame = NSRect(x: 18, y: 275, width: 230, height: 18); background.addSubview(summary)
        let close = NSButton(title: "×", target: self, action: #selector(closeContextMenu))
        close.isBordered = false; close.font = .systemFont(ofSize: 20)
        close.setAccessibilityLabel("关闭菜单"); close.frame = NSRect(x: 224, y: 295, width: 25, height: 25)
        background.addSubview(close)
        let items: [(String, Selector)] = [
            (panel.isVisible ? "隐藏悬浮球" : "显示悬浮球", #selector(toggle)),
            ("回到右上角", #selector(resetPosition)),
            ("打开详细流量面板…", #selector(openDetails)),
            ("设置每日限额…", #selector(showLimitSettings)),
            ("测试限额提醒…", #selector(testAlert)),
            ("退出悬浮球", #selector(quit))
        ]
        for (index, item) in items.enumerated() {
            let button = NSButton(title: item.0, target: self, action: item.1)
            button.bezelStyle = .rounded; button.font = .systemFont(ofSize: 13)
            button.frame = NSRect(x: 14, y: 228 - CGFloat(index) * 38, width: frame.width - 28, height: 31)
            background.addSubview(button)
        }
        popup.contentView = background; menuPanel = popup
        NSApp.activate(ignoringOtherApps: true)
        popup.makeKeyAndOrderFront(nil)
    }
    @objc func toggle() { closeContextMenu(); if panel.isVisible { panel.orderOut(nil) } else { panel.orderFrontRegardless() } }
    @objc func resetPosition() { closeContextMenu(); position(reset: true); panel.orderFrontRegardless() }
    @objc func openDetails() { closeContextMenu(); NSWorkspace.shared.open(URL(string: "http://127.0.0.1:\(Paths.port)/")!) }
    @objc func quit() { NSApp.terminate(nil) }
    @objc func dismissAlert() { alertPanel?.close(); alertPanel = nil }
    func configuredDailyLimit() -> Double {
        if let data = try? Data(contentsOf: root.appendingPathComponent("settings.json")),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let value = object["daily_limit_gb"] as? Double { return value }
        return (orb.sample?.quota.limit_bytes ?? 80e9) / 1e9
    }
    @objc func showLimitSettings() {
        closeContextMenu()
        if let settingsPanel, settingsPanel.isVisible { settingsPanel.makeKeyAndOrderFront(nil); return }
        let window = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 390, height: 250), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = "设置每日限额"; window.isReleasedWhenClosed = false
        window.level = .modalPanel; window.appearance = NSAppearance(named: .aqua)
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        let view = NSView(frame: NSRect(x: 0, y: 0, width: 390, height: 250))
        let heading = NSTextField(labelWithString: "每日代理流量限额")
        heading.font = .boldSystemFont(ofSize: 17); heading.frame = NSRect(x: 24, y: 201, width: 340, height: 24)
        let field = NSTextField(string: limitNumber(configuredDailyLimit()))
        field.font = .monospacedDigitSystemFont(ofSize: 20, weight: .medium)
        field.frame = NSRect(x: 24, y: 151, width: 260, height: 34)
        field.setAccessibilityLabel("每日限额，单位 GB")
        let unit = NSTextField(labelWithString: "GB / 天")
        unit.font = .systemFont(ofSize: 13); unit.frame = NSRect(x: 298, y: 160, width: 75, height: 19)
        let detail = NSTextField(wrappingLabelWithString: "按上传 + 下载统计，每天 00:00 重新计数。\n达到 80%、95%、100% 时提醒，修改后立即生效。")
        detail.font = .systemFont(ofSize: 12); detail.textColor = .secondaryLabelColor
        detail.frame = NSRect(x: 24, y: 97, width: 345, height: 42)
        let error = NSTextField(labelWithString: "")
        error.font = .systemFont(ofSize: 11); error.textColor = .systemRed
        error.frame = NSRect(x: 24, y: 62, width: 345, height: 27)
        let cancel = NSButton(title: "取消", target: self, action: #selector(cancelLimitSettings))
        cancel.bezelStyle = .rounded; cancel.keyEquivalent = "\u{1b}"; cancel.frame = NSRect(x: 176, y: 20, width: 90, height: 32)
        let save = NSButton(title: "保存", target: self, action: #selector(saveLimitSettings))
        save.bezelStyle = .rounded; save.keyEquivalent = "\r"; save.frame = NSRect(x: 278, y: 20, width: 90, height: 32)
        for child in [heading, field, unit, detail, error, cancel, save] as [NSView] { view.addSubview(child) }
        limitField = field; limitError = error; settingsPanel = window; window.contentView = view
        window.center(); NSApp.activate(ignoringOtherApps: true); window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(field)
    }
    @objc func cancelLimitSettings() { settingsPanel?.close(); settingsPanel = nil }
    @objc func saveLimitSettings() {
        do {
            _ = try saveDailyLimit(limitField?.stringValue ?? "", to: root.appendingPathComponent("settings.json"))
            cancelLimitSettings()
            poll()
        } catch { limitError?.stringValue = error.localizedDescription }
    }
    @objc func testAlert() {
        closeContextMenu()
        // Preview has no side effects on usage or the real notification ledger.
        let limit = configuredDailyLimit() * 1e9
        let example = QuotaStatus(day: "预览", limit_bytes: limit, used_bytes: limit * 0.95, remaining_bytes: limit * 0.05, percent: 95, stage: 95)
        showQuotaAlert(example, preview: true)
    }
    func checkQuota(_ quota: QuotaStatus) {
        let acknowledged = UserDefaults.standard.double(forKey: quota.acknowledgementKey)
        guard pendingQuotaAlert(stage: quota.stage, acknowledged: acknowledged) else { return }
        UserDefaults.standard.set(quota.stage, forKey: quota.acknowledgementKey)
        showQuotaAlert(quota, preview: false)
    }
    func showQuotaAlert(_ quota: QuotaStatus, preview: Bool) {
        alertPanel?.close()
        let window = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 390, height: 212), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = preview ? "流量提醒预览" : "每日流量提醒"
        window.isReleasedWhenClosed = false; window.level = .modalPanel
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        let view = NSView(frame: NSRect(x: 0, y: 0, width: 390, height: 212))
        let heading = NSTextField(labelWithString: (preview ? "[测试] " : "") + (quota.percent >= 100 ? "今日流量已达到限额" : "今日流量接近限额"))
        heading.font = .boldSystemFont(ofSize: 18); heading.frame = NSRect(x: 24, y: 160, width: 350, height: 28)
        let message = NSTextField(wrappingLabelWithString: String(format: "今日代理上传 + 下载已用 %@（%.0f%%）\n每日限额：%@　剩余：%@\n每天 00:00 重新统计；本提醒不会断开网络。", decimalGB(quota.used_bytes), quota.percent, decimalGB(quota.limit_bytes), decimalGB(quota.remaining_bytes)))
        message.font = .systemFont(ofSize: 13); message.frame = NSRect(x: 24, y: 68, width: 342, height: 84)
        let button = NSButton(title: "知道了", target: self, action: #selector(dismissAlert))
        button.bezelStyle = .rounded; button.keyEquivalent = "\r"; button.frame = NSRect(x: 278, y: 20, width: 90, height: 32)
        view.addSubview(heading); view.addSubview(message); view.addSubview(button)
        window.contentView = view; window.center(); alertPanel = window
        NSApp.activate(ignoringOtherApps: true); window.makeKeyAndOrderFront(nil)
        NSSound(named: NSSound.Name("Glass"))?.play()
    }
    func startCollector() {
        guard launches < 3, FileManager.default.fileExists(atPath: Paths.collector.path) else { return }
        launches += 1
        let process = Process(); process.executableURL = Paths.collector
        process.arguments = []
        process.currentDirectoryURL = root
        process.standardOutput = FileHandle.nullDevice; process.standardError = FileHandle.nullDevice
        do { try process.run() } catch { NSLog("Unable to start local collector: %@", error.localizedDescription) }
    }
    func poll() {
        guard !loading else { return }; loading = true
        session.dataTask(with: endpoint) { [weak self] data, response, error in
            let result = data.flatMap { try? JSONDecoder().decode(Sample.self, from: $0) }
            DispatchQueue.main.async {
                guard let self else { return }; self.loading = false
                if let result {
                    self.orb.sample = result; self.orb.unavailable = false; self.lastSuccess = Date(); self.launches = 0
                    let up = quantity(result.speed.proxy.up, rate: true), down = quantity(result.speed.proxy.down, rate: true)
                    self.orb.setAccessibilityValue("\(result.online ? "在线" : "离线")，上传 \(up)，下载 \(down)，今日 \(decimalGB(result.quota.used_bytes))，限额 \(decimalGB(result.quota.limit_bytes))")
                    self.status.button?.toolTip = "上传 \(up) · 下载 \(down) · 今日 \(decimalGB(result.quota.used_bytes)) / \(decimalGB(result.quota.limit_bytes))"
                    self.checkQuota(result.quota)
                } else {
                    if Date().timeIntervalSince(self.lastSuccess) > 4 { self.orb.unavailable = true }
                    self.startCollector()
                }
                self.orb.needsDisplay = true
            }
        }.resume()
    }
}

@main
struct TrafficOrbMain {
    static func main() {
        if CommandLine.arguments.contains("--check-package") {
            do {
                try Paths.prepare()
                let ok = FileManager.default.isExecutableFile(atPath: Paths.collector.path)
                    && FileManager.default.fileExists(atPath: Paths.supportRoot.appendingPathComponent("settings.json").path)
                print(ok ? "PASS: bundled collector and per-user settings" : "FAIL: incomplete app bundle")
                if !ok { exit(1) }
            } catch { print("FAIL: unable to initialize per-user settings"); exit(1) }
            return
        }
        let delegate = AppDelegate()
        NSApplication.shared.delegate = delegate
        withExtendedLifetime(delegate) { NSApplication.shared.run() }
    }
}
