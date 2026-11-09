import Cocoa

func contextMenuFrame(anchor: NSRect, screen: NSRect) -> NSRect {
    let margin: CGFloat = 8
    let size = NSSize(width: min(264, screen.width - 2 * margin), height: min(332, screen.height - 2 * margin))
    let x = min(max(anchor.maxX - size.width, screen.minX + margin), screen.maxX - size.width - margin)
    let below = anchor.minY - size.height - 6
    let preferredY = below >= screen.minY + margin ? below : anchor.maxY + 6
    let y = min(max(preferredY, screen.minY + margin), screen.maxY - size.height - margin)
    return NSRect(origin: NSPoint(x: x, y: y), size: size)
}

final class ContextMenuPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
    override func resignKey() {
        super.resignKey()
        orderOut(nil)
    }
    override func cancelOperation(_ sender: Any?) { orderOut(nil) }
}
