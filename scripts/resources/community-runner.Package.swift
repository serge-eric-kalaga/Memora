// swift-tools-version: 6.2
import PackageDescription
let package = Package(
    name: "MemoraCommunity", platforms: [.macOS(.v15)],
    dependencies: [.package(path: "../sdk")],
    targets: [.executableTarget(name: "memora-community", dependencies: [
        .product(name: "FluidAudio", package: "sdk")
    ])]
)
