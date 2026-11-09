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
    static func prepare() throws {
        try FileManager.default.createDirectory(at: supportRoot, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let settings = supportRoot.appendingPathComponent("settings.json")
        if !FileManager.default.fileExists(atPath: settings.path) {
            let defaults = applicationBundle.appendingPathComponent("Contents/Resources/default-settings.json")
            try FileManager.default.copyItem(at: defaults, to: settings)
        }
    }
}
