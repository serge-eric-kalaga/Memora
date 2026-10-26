import Foundation
import CoreML
import FluidAudio

enum InputError: Error { case invalidArguments, invalidAudio, invalidParameters }

/// Deliberately offline: Core ML models are loaded directly from verified local bundles.
@main struct MemoraCommunity {
    static func main() async {
        do { try await run() }
        catch { FileHandle.standardError.write(Data("Community diarization failed: \(error)\n".utf8)); exit(1) }
    }
    static func run() async throws {
        let args = CommandLine.arguments
        guard args.count == 4 || args.count == 5 else { throw InputError.invalidArguments }
        ModelHub.offlineMode = true
        let directory = URL(fileURLWithPath: args[1])
        let input = URL(fileURLWithPath: args[2])
        let bytes = try input.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
        guard bytes > 0, bytes <= 16_000 * 4 * 7_200, bytes % 4 == 0 else { throw InputError.invalidAudio }
        let data = try Data(contentsOf: input)
        var audio = [Float](repeating: 0, count: data.count / 4)
        _ = audio.withUnsafeMutableBytes { data.copyBytes(to: $0) }
        guard audio.allSatisfy({ $0.isFinite && abs($0) <= 1.01 }) else { throw InputError.invalidAudio }
        let cfg = MLModelConfiguration(); cfg.computeUnits = .all
        func load(_ name: String) throws -> MLModel {
            try MLModel(contentsOf: directory.appendingPathComponent(name + ".mlmodelc"), configuration: cfg)
        }
        let parameterData = try Data(contentsOf: directory.appendingPathComponent("plda-parameters.json"))
        guard let parameters = try JSONSerialization.jsonObject(with: parameterData) as? [String: Any],
              let tensors = parameters["tensors"] as? [String: Any],
              let psi = tensors["psi"] as? [String: Any],
              let encoded = psi["data_base64"] as? String,
              let decoded = Data(base64Encoded: encoded),
              decoded.count > 0, decoded.count <= 65_536, decoded.count % 4 == 0 else { throw InputError.invalidParameters }
        var floats = [Float](repeating: 0, count: decoded.count / 4)
        _ = floats.withUnsafeMutableBytes { decoded.copyBytes(to: $0) }
        guard floats.allSatisfy({ $0.isFinite }) else { throw InputError.invalidParameters }
        let models = OfflineDiarizerModels(
            segmentationModel: try load("Segmentation"), fbankModel: try load("FBank"),
            embeddingModel: try load("Embedding"), pldaRhoModel: try load("PldaRho"),
            pldaPsi: floats.map(Double.init), compilationDuration: 0)
        var settings = OfflineDiarizerConfig.default
        if args.count == 5 {
            guard let count = Int(args[4]), (1...8).contains(count) else { throw InputError.invalidArguments }
            settings = settings.withSpeakers(exactly: count)
        }
        let manager = OfflineDiarizerManager(config: settings); manager.initialize(models: models)
        let start = Date(); let result = try await manager.process(audio: audio)
        let turns: [[String: Any]] = result.segments.map {
            ["start": Double($0.startTimeSeconds), "end": Double($0.endTimeSeconds),
             "speaker_id": $0.speakerId, "uncertain": false]
        }
        let output: [String: Any] = ["turns": turns, "seconds": Date().timeIntervalSince(start),
            "speaker_count": Set(result.segments.map { $0.speakerId }).count]
        try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
            .write(to: URL(fileURLWithPath: args[3]), options: [.atomic])
    }
}
