// swift-tools-version: 6.2
// Memora minimal build manifest: omit unrelated TTS binary artifact; source code unchanged.
import PackageDescription
let package = Package(name: "FluidAudio", platforms: [.macOS(.v15)], products: [.library(name: "FluidAudio", targets: ["FluidAudio"])], targets: [
 .target(name:"FluidAudio",dependencies:["FastClusterWrapper","MachTaskSelfWrapper"],path:"Sources/FluidAudio",exclude:["ASR/Parakeet/Unified/benchmark.md"],resources:[.process("TTS/LuxTts/G2p/Resources")]),
 .target(name:"FastClusterWrapper",path:"Sources/FastClusterWrapper",publicHeadersPath:"include"),
 .target(name:"MachTaskSelfWrapper",path:"Sources/MachTaskSelfWrapper",publicHeadersPath:"include")
], cxxLanguageStandard:.cxx17)
