"""Install the pinned offline Core ML/VBx recovery runner (macOS 15+, Swift 6.2).

No service activation. --from-lab reuses local checked downloads without network.
The build keeps upstream Sources unchanged and uses a minimal Swift package to
omit unrelated TTS binary dependencies. Locally built binary hashes attest local
integrity, not an upstream signed/reproducible executable.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "scripts/resources"
MODEL_MANIFEST = RESOURCES / "community-models.json"
SDK_SOURCE = "https://api.github.com/repos/FluidInference/FluidAudio/tarball/v0.17.7"
SDK_SHA = "77467b4ebebbc29cf328758378cfc99af60a9a5b9983b0b6e0a2295b9409bc52"
SDK_BYTES = 6664121
SDK_PREFIX = "FluidInference-FluidAudio-2437bf2/"
SDK_COMMIT = "503b4bd1bbf7220882de39fe8ae6716aae4132da"
SDK_LICENSE_SHA = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
SDK_LICENSE_BYTES = 11357
TRUSTED_HOSTS = {
    "api.github.com",
    "codeload.github.com",
    "github.com",
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.huggingface.co",
    "cas-bridge.xethub.hf.co",
    "us.aws.cdn.hf.co",
}
BUILD_RESOURCES = (
    "community-sdk.Package.swift",
    "community-runner.Package.swift",
    "community-runner.swift",
)


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def safe_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Refusing a symlink path")
    return path


def verify(path, size, sha):
    path = safe_path(path)
    if not path.is_file() or path.stat().st_size != size or digest(path) != sha:
        raise ValueError("Asset integrity check failed")


def relative(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError("Unsafe asset path")
    return Path(*p.parts)


def check_url(url):
    p = urllib.parse.urlsplit(url)
    if (
        p.scheme != "https"
        or p.hostname not in TRUSTED_HOSTS
        or p.username
        or p.password
        or p.port not in (None, 443)
    ):
        raise ValueError("Untrusted download URL")


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, destination, size, sha):
    check_url(url)
    opener = urllib.request.build_opener(Redirects())
    with opener.open(url, timeout=60) as response, destination.open("xb") as output:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > size:
                raise ValueError("Download exceeds pinned size")
            output.write(chunk)
    verify(destination, size, sha)


def model_spec():
    safe_path(MODEL_MANIFEST)
    data = json.loads(MODEL_MANIFEST.read_text())
    names = set()
    for f in data["files"]:
        relative(f["path"])
        if (
            f["path"] in names
            or not 0 < f["bytes"] <= 32 * 1024 * 1024
            or not re.fullmatch("[a-f0-9]{64}", f["sha256"])
        ):
            raise ValueError("Invalid pinned model manifest")
        names.add(f["path"])
    if (
        not re.fullmatch("[a-f0-9]{40}", data["revision"])
        or data["repo"] != "FluidInference/speaker-diarization-coreml"
    ):
        raise ValueError("Invalid model source")
    return data


def check_models(folder):
    safe_path(folder)
    spec = model_spec()
    verify(
        folder / "manifest.json", MODEL_MANIFEST.stat().st_size, digest(MODEL_MANIFEST)
    )
    for f in spec["files"]:
        verify(folder / relative(f["path"]), f["bytes"], f["sha256"])


def prepare_models(folder, lab=None, check_only=False):
    folder = safe_path(folder)
    if folder.exists():
        check_models(folder)
        return
    if check_only:
        raise ValueError("Local community models not installed")
    folder.parent.mkdir(parents=True, exist_ok=True)
    spec = model_spec()
    with tempfile.TemporaryDirectory(
        prefix=".community-models-", dir=folder.parent
    ) as temp:
        stage = Path(temp) / "models"
        stage.mkdir()
        for f in spec["files"]:
            path = relative(f["path"])
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.as_posix() == "LICENSE":
                source = RESOURCES / "community-LICENSE.txt"
                verify(source, f["bytes"], f["sha256"])
                shutil.copyfile(source, target)
            elif lab is not None:
                source = Path(lab) / "models" / path
                verify(source, f["bytes"], f["sha256"])
                shutil.copyfile(source, target)
            else:
                url = f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{path.as_posix()}"
                download(url, target, f["bytes"], f["sha256"])
        shutil.copyfile(MODEL_MANIFEST, stage / "manifest.json")
        check_models(stage)
        if folder.exists():
            raise ValueError("Concurrent community model installation")
        stage.rename(folder)


def extract_sdk(archive, folder):
    verify(archive, SDK_BYTES, SDK_SHA)
    selected = []
    seen = set()
    with tarfile.open(archive, "r:gz") as handle:
        for member in handle:
            if member.name == SDK_PREFIX.rstrip("/") and member.isdir():
                continue
            if not member.name.startswith(SDK_PREFIX):
                raise ValueError("Unexpected SDK archive prefix")
            name = member.name[len(SDK_PREFIX) :]
            if not name:
                continue
            path = relative(name)
            if (
                member.issym()
                or member.islnk()
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("SDK archive links or special files forbidden")
            if member.isdir():
                continue
            if not (
                name == "LICENSE"
                or any(
                    name.startswith("Sources/" + s + "/")
                    for s in ("FluidAudio", "FastClusterWrapper", "MachTaskSelfWrapper")
                )
            ):
                continue
            if name in seen or member.size > 32 * 1024 * 1024:
                raise ValueError("Invalid SDK member")
            seen.add(name)
            selected.append(member)
            if (
                len(selected) > 5000
                or sum(m.size for m in selected) > 128 * 1024 * 1024
            ):
                raise ValueError("SDK extraction exceeds limit")
            target = folder / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with handle.extractfile(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    if "LICENSE" not in seen or not any(
        n.startswith("Sources/FluidAudio/") for n in seen
    ):
        raise ValueError("Incomplete SDK source")


def host_check():
    if (
        platform.system() != "Darwin"
        or platform.machine() != "arm64"
        or int(platform.mac_ver()[0].split(".")[0] or "0") < 15
    ):
        raise ValueError("Community runner requires Apple Silicon macOS 15+")
    result = subprocess.run(
        ["swift", "--version"], capture_output=True, text=True, check=True, timeout=30
    )
    match = re.search(r"Swift version (\d+)\.(\d+)", result.stdout)
    if not match or tuple(map(int, match.groups())) < (6, 2):
        raise ValueError("Community runner requires Swift 6.2+")
    return result.stdout.strip()


def resource_hashes():
    return {name: digest(safe_path(RESOURCES / name)) for name in BUILD_RESOURCES}


def check_tooling(folder):
    safe_path(folder)
    manifest_path = safe_path(folder / "manifest.json")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("sdk_sha256") != SDK_SHA
        or manifest.get("resources") != resource_hashes()
        or manifest.get("model_manifest_sha256") != digest(MODEL_MANIFEST)
    ):
        raise ValueError("Community runner provenance mismatch")
    binary = manifest["binary"]
    if (
        binary.get("path") != "memora-community"
        or not isinstance(binary.get("bytes"), int)
        or not re.fullmatch("[a-f0-9]{64}", binary.get("sha256", ""))
    ):
        raise ValueError("Invalid community executable manifest")
    verify(folder / binary["path"], binary["bytes"], binary["sha256"])
    if not os.access(folder / binary["path"], os.X_OK):
        raise ValueError("Community runner is not executable")
    verify(folder / "SDK-LICENSE", SDK_LICENSE_BYTES, SDK_LICENSE_SHA)


def prepare_tooling(folder, lab=None, check_only=False):
    folder = safe_path(folder)
    if folder.exists():
        check_tooling(folder)
        return
    if check_only:
        raise ValueError("Local community runner not installed")
    swift_version = host_check()
    folder.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".community-build-", dir=folder.parent
    ) as temp:
        work = Path(temp)
        if lab is not None:
            archive = Path(lab) / "source.tar.gz"
        else:
            archive = work / "source.tar.gz"
            download(SDK_SOURCE, archive, SDK_BYTES, SDK_SHA)
        sdk = work / "sdk"
        sdk.mkdir()
        extract_sdk(archive, sdk)
        shutil.copyfile(
            RESOURCES / "community-sdk.Package.swift", sdk / "Package.swift"
        )
        runner = work / "runner"
        sources = runner / "Sources/memora-community"
        sources.mkdir(parents=True)
        shutil.copyfile(
            RESOURCES / "community-runner.Package.swift", runner / "Package.swift"
        )
        shutil.copyfile(RESOURCES / "community-runner.swift", sources / "Runner.swift")
        # No external package URLs in the shipped manifests; upstream code remains unchanged.
        with (work / "build.log").open("wb") as log:
            try:
                subprocess.run(
                    ["swift", "build", "--package-path", str(runner), "-c", "release"],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=900,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                log.flush()
                # Compiler output concerns only public SDK/runner source, never audio.
                with (work / "build.log").open("rb") as diagnostics:
                    diagnostics.seek(max(0, (work / "build.log").stat().st_size - 6000))
                    detail = diagnostics.read().decode("utf-8", errors="replace")
                raise ValueError(
                    "Community runner build failed; verify Swift/Xcode compatibility\n"
                    + detail
                ) from error
        stage = work / "installed"
        stage.mkdir()
        shutil.copyfile(
            runner / ".build/release/memora-community", stage / "memora-community"
        )
        (stage / "memora-community").chmod(
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IXGRP
            | stat.S_IROTH
            | stat.S_IXOTH
        )
        shutil.copyfile(sdk / "LICENSE", stage / "SDK-LICENSE")
        binary = stage / "memora-community"
        manifest = {
            "sdk_commit": SDK_COMMIT,
            "sdk_sha256": SDK_SHA,
            "resources": resource_hashes(),
            "model_manifest_sha256": digest(MODEL_MANIFEST),
            "swift": swift_version,
            "binary": {
                "path": binary.name,
                "bytes": binary.stat().st_size,
                "sha256": digest(binary),
            },
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        check_tooling(stage)
        if folder.exists():
            raise ValueError("Concurrent community runner installation")
        stage.rename(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-lab",
        type=Path,
        help="Reuse verified source.tar.gz and models/ without downloads",
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    models = Path(
        os.environ.get(
            "MEMORA_COMMUNITY_MODEL_DIR", ROOT / ".memora/models/community-coreml"
        )
    )
    tooling = Path(
        os.environ.get(
            "MEMORA_COMMUNITY_TOOL_DIR", ROOT / ".memora/tooling/community-coreml"
        )
    )
    prepare_models(models, args.from_lab, args.check_only)
    prepare_tooling(tooling, args.from_lab, args.check_only)
    print("Offline Core ML community assets and runner verified; no service activated.")


if __name__ == "__main__":
    main()
