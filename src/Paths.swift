import Foundation

enum Paths {
    static let applicationID = "app.trafficorb.client"
    static let supportRoot: URL = {
        if let path = ProcessInfo.processInfo.environment["TRAFFIC_ORB_HOME"] { return URL(fileURLWithPath: path) }
        return FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("TrafficOrb")
    }()
    static let port = Int(ProcessInfo.processInfo.environment["TRAFFIC_ORB_PORT"] ?? "18863") ?? 18863
    static let executableRoot = URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent()
    static let applicationBundle = executableRoot.deletingLastPathComponent().deletingLastPathComponent()
    static let collector = executableRoot.appendingPathComponent("TrafficOrbCollector")
    static var lastGuardLaunch = Date.distantPast
    static func processCommand(_ pid: Int32) -> String? {
        let task = Process(), output = Pipe()
        task.executableURL = URL(fileURLWithPath: "/bin/ps")
        task.arguments = ["-p", String(pid), "-o", "args="]
        task.standardOutput = output; task.standardError = FileHandle.nullDevice
        do {
            try task.run()
            let data = output.fileHandleForReading.readDataToEndOfFile()
            task.waitUntilExit()
            return String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
        } catch { return nil }
    }
    static func ensureGuard() {
        let file = supportRoot.appendingPathComponent("data/proxy-guard/guard.pid")
        if let raw = try? String(contentsOf: file, encoding: .utf8),
           let pid = Int32(raw.trimmingCharacters(in: .whitespacesAndNewlines)),
           processCommand(pid)?.hasSuffix(collector.path + " --guard") == true { return }
        guard Date().timeIntervalSince(lastGuardLaunch) > 15 else { return }
        lastGuardLaunch = Date()
        let task = Process(); task.executableURL = collector; task.arguments = ["--guard"]
        task.standardOutput = FileHandle.nullDevice; task.standardError = FileHandle.nullDevice
        do { try task.run() } catch { NSLog("Unable to launch proxy protection: %@", error.localizedDescription) }
    }
    static func prepare() throws {
        try FileManager.default.createDirectory(at: supportRoot, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let settings = supportRoot.appendingPathComponent("settings.json")
        if !FileManager.default.fileExists(atPath: settings.path) {
            let defaults = applicationBundle.appendingPathComponent("Contents/Resources/default-settings.json")
            try FileManager.default.copyItem(at: defaults, to: settings)
        }
        let protection = supportRoot.appendingPathComponent("proxy-guard-settings.json")
        if !FileManager.default.fileExists(atPath: protection.path) {
            try FileManager.default.copyItem(at: applicationBundle.appendingPathComponent("Contents/Resources/default-proxy-guard-settings.json"), to: protection)
        }
    }
}
