import Cocoa

// A small login-session helper: observes app lifecycle without changing v2rayN.
final class LifecycleWatcher {
    let bundleID = "2dust.v2rayN"
    let root = Paths.supportRoot
    var previous: Set<pid_t> = []
    var timer: Timer?
    var observers: [NSObjectProtocol] = []

    func run() {
        let center = NSWorkspace.shared.notificationCenter
        for name in [NSWorkspace.didLaunchApplicationNotification, NSWorkspace.didTerminateApplicationNotification] {
            observers.append(center.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in self?.reconcile() })
        }
        reconcile()
        timer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { [weak self] _ in self?.reconcile() }
        RunLoop.main.run()
    }

    func reconcile() {
        let current = Set(NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).filter { !$0.isTerminated }.map(\.processIdentifier))
        if !current.isEmpty && (previous.isEmpty || current != previous) {
            let config = NSWorkspace.OpenConfiguration()
            config.activates = false
            NSWorkspace.shared.openApplication(at: Paths.applicationBundle, configuration: config) { _, error in
                if let error { NSLog("Unable to launch orb: %@", error.localizedDescription) }
            }
        } else if current.isEmpty && !previous.isEmpty {
            stopCompanions()
        }
        previous = current
    }

    func stopCompanions() {
        for app in NSRunningApplication.runningApplications(withBundleIdentifier: Paths.applicationID) { app.terminate() }
        // Only signal the collector that belongs to this installation.
        guard let raw = try? String(contentsOf: root.appendingPathComponent("data/server.pid"), encoding: .utf8),
              let pid = Int32(raw.trimmingCharacters(in: .whitespacesAndNewlines)), pid > 1 else { return }
        let check = Process(); let output = Pipe()
        check.executableURL = URL(fileURLWithPath: "/bin/ps")
        check.arguments = ["-p", String(pid), "-o", "args="]
        check.standardOutput = output; check.standardError = FileHandle.nullDevice
        do {
            try check.run()
            let data = output.fileHandleForReading.readDataToEndOfFile()
            check.waitUntilExit()
            let command = String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
            if command.hasSuffix(Paths.collector.path) { kill(pid, SIGTERM) }
        } catch { NSLog("Unable to inspect collector: %@", error.localizedDescription) }
    }
}

@main
struct WatcherMain {
    static func main() {
        let watcher = LifecycleWatcher()
        if CommandLine.arguments.contains("--stop-companions") { watcher.stopCompanions() }
        else { watcher.run() }
    }
}
