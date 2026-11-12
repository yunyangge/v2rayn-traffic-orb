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
        if !current.isEmpty { try? Paths.prepare(); Paths.ensureGuard() }
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
        // Match executable plus mode so unrelated reused PIDs are never signalled.
        for (file, suffix) in [("data/server.pid", Paths.collector.path),
                               ("data/proxy-guard/guard.pid", Paths.collector.path + " --guard")] {
            guard let raw = try? String(contentsOf: root.appendingPathComponent(file), encoding: .utf8),
                  let pid = Int32(raw.trimmingCharacters(in: .whitespacesAndNewlines)), pid > 1,
                  Paths.processCommand(pid)?.hasSuffix(suffix) == true else { continue }
            kill(pid, SIGTERM)
        }
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
