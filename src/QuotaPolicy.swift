import Foundation

struct QuotaStatus: Decodable {
    let day: String
    let limit_bytes: Double
    let used_bytes: Double
    let remaining_bytes: Double
    let percent: Double
    let stage: Double
    var acknowledgementKey: String { "quotaAlert:\(day):\(Int64(limit_bytes))" }
}

func pendingQuotaAlert(stage: Double, acknowledged: Double) -> Bool {
    stage > 0 && stage > acknowledged
}

func decimalGB(_ bytes: Double) -> String { String(format: "%.1f GB", bytes / 1_000_000_000) }

enum LimitSettingError: LocalizedError {
    case invalidNumber
    var errorDescription: String? { "请输入 0.1～1,000,000 之间的数字，单位为 GB。" }
}

func parseDailyLimit(_ text: String) throws -> Double {
    guard let value = Double(text.trimmingCharacters(in: .whitespacesAndNewlines)),
          value.isFinite, value >= 0.1, value <= 1_000_000 else { throw LimitSettingError.invalidNumber }
    return value
}

func limitNumber(_ value: Double) -> String {
    let formatter = NumberFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.numberStyle = .decimal
    formatter.usesGroupingSeparator = false
    formatter.maximumFractionDigits = 6
    return formatter.string(from: NSNumber(value: value)) ?? String(value)
}

func saveDailyLimit(_ text: String, to url: URL) throws -> Double {
    let value = try parseDailyLimit(text)
    let data = try Data(contentsOf: url)
    guard var settings = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
        throw CocoaError(.fileReadCorruptFile)
    }
    settings["daily_limit_gb"] = value
    let updated = try JSONSerialization.data(withJSONObject: settings, options: [.prettyPrinted, .sortedKeys])
    try updated.write(to: url, options: .atomic)
    return value
}
