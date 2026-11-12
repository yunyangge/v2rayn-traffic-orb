import Foundation

struct ProtectionSettings: Decodable {
    var enabled: Bool
    var limit_bytes: Double
    var window_seconds: Double
    var restart_block_seconds: Double
}

struct ProtectedProcess: Decodable {
    let label: String
    let bytes: Double
    let pid: Int
}

struct ProtectionEvent: Decodable {
    let time: Double
    let event: String
    let label: String?
    let reason: String?
}

struct ProtectionStatus: Decodable {
    let updated: Double
    let enabled: Bool
    let route_error: String
    let top: [ProtectedProcess]
    let recent_events: [ProtectionEvent]
}

func readProtectionSettings(root: URL) -> ProtectionSettings {
    guard let data = try? Data(contentsOf: root.appendingPathComponent("proxy-guard-settings.json")),
          let result = try? JSONDecoder().decode(ProtectionSettings.self, from: data) else {
        return ProtectionSettings(enabled: false, limit_bytes: 5e9, window_seconds: 3600, restart_block_seconds: 3600)
    }
    return result
}

func saveProtectionSettings(root: URL, enabled: Bool, limit: String) throws {
    let gb = try parseDailyLimit(limit)
    let url = root.appendingPathComponent("proxy-guard-settings.json")
    let data = try Data(contentsOf: url)
    guard var object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
        throw CocoaError(.fileReadCorruptFile)
    }
    object["enabled"] = enabled
    object["limit_bytes"] = gb * 1e9
    try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
}
