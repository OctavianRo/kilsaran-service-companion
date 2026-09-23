// Read-only OCR for scanned PDF pages using macOS Vision. No cloud upload.
import Foundation
import PDFKit
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count >= 2, let pdf = PDFDocument(url: URL(fileURLWithPath: args[1])) else { exit(1) }
let pages = args.count > 2 ? args[2].split(separator: ",").compactMap { Int($0) } : Array(1...pdf.pageCount)
var results: [[String: Any]] = []
for n in pages {
    guard let page = pdf.page(at: n - 1) else { continue }
    let bounds = page.bounds(for: .mediaBox)
    let scale: CGFloat = 2.5
    let width = Int(bounds.width * scale), height = Int(bounds.height * scale)
    guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { continue }
    ctx.setFillColor(NSColor.white.cgColor); ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))
    ctx.scaleBy(x: scale, y: scale); page.draw(with: .mediaBox, to: ctx)
    guard let image = ctx.makeImage() else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["en-GB"]
    req.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: image).perform([req])
    let lines = (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    results.append(["page": n, "text": lines.joined(separator: "\n")])
    if let path = ProcessInfo.processInfo.environment["OCR_PREVIEW"], n == pages.first {
        let rep = NSBitmapImageRep(cgImage: image)
        try rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: path))
    }
}
let data = try JSONSerialization.data(withJSONObject: results, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
