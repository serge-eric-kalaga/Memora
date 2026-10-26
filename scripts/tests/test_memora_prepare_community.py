"""Small synthetic assets only: no network, Swift compilation or real models."""

import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "memora-prepare-community.py"
spec = importlib.util.spec_from_file_location("prepare_community_test", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def archive(path, files):
    with tarfile.open(path, "w:gz") as target:
        for name, data, kind in files:
            member = tarfile.TarInfo(m.SDK_PREFIX + name)
            member.type = kind
            member.size = len(data) if kind == tarfile.REGTYPE else 0
            member.linkname = "../outside"
            target.addfile(member, io.BytesIO(data) if member.isfile() else None)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    resources = tmp_path / "resources"
    resources.mkdir()
    lab = tmp_path / "lab"
    (lab / "models").mkdir(parents=True)
    entries = []
    for name, data in [
        ("Synthetic.mlmodelc/weights.bin", b"synthetic weights"),
        ("NOTICE.md", b"Synthetic attribution"),
        ("LICENSE", b"Synthetic license"),
    ]:
        target = lab / "models" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entries.append({"path": name, "bytes": len(data), "sha256": sha(data)})
    (resources / "community-LICENSE.txt").write_bytes(b"Synthetic license")
    manifest = resources / "community-models.json"
    manifest.write_text(
        json.dumps(
            {
                "repo": "FluidInference/speaker-diarization-coreml",
                "revision": "a" * 40,
                "files": entries,
            }
        )
    )
    for name in m.BUILD_RESOURCES:
        (resources / name).write_text("synthetic build resource")
    source = lab / "source.tar.gz"
    archive(
        source,
        [
            ("LICENSE", b"Apache synthetic", tarfile.REGTYPE),
            ("Sources/FluidAudio/Example.swift", b"synthetic Swift", tarfile.REGTYPE),
        ],
    )
    monkeypatch.setattr(m, "RESOURCES", resources)
    monkeypatch.setattr(m, "MODEL_MANIFEST", manifest)
    monkeypatch.setattr(m, "SDK_BYTES", source.stat().st_size)
    monkeypatch.setattr(m, "SDK_SHA", m.digest(source))
    monkeypatch.setattr(m, "SDK_LICENSE_BYTES", len(b"Apache synthetic"))
    monkeypatch.setattr(m, "SDK_LICENSE_SHA", sha(b"Apache synthetic"))
    monkeypatch.setattr(m, "host_check", lambda: "Swift version 6.2 synthetic")
    monkeypatch.setattr(m, "download", lambda *args: pytest.fail("Network not allowed"))

    def build(command, **kwargs):
        runner = Path(command[command.index("--package-path") + 1])
        binary = runner / ".build/release/memora-community"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"synthetic executable")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(m.subprocess, "run", build)
    return tmp_path, lab


def test_offline_install_and_check_only_are_idempotent(setup, monkeypatch):
    root, lab = setup
    models, tooling = root / "models", root / "tooling"
    m.prepare_models(models, lab)
    m.prepare_tooling(tooling, lab)
    before = (tooling / "manifest.json").read_bytes()
    monkeypatch.setattr(
        m, "host_check", lambda: pytest.fail("Check-only must not call Swift")
    )
    m.prepare_models(models, check_only=True)
    m.prepare_tooling(tooling, check_only=True)
    assert (tooling / "manifest.json").read_bytes() == before
    assert (models / "manifest.json").read_bytes() == m.MODEL_MANIFEST.read_bytes()
    assert (tooling / "SDK-LICENSE").read_bytes() == b"Apache synthetic"


@pytest.mark.parametrize("prepare", [m.prepare_models, m.prepare_tooling])
def test_check_only_missing_never_installs(setup, prepare):
    root, _ = setup
    with pytest.raises(ValueError, match="not installed"):
        prepare(root / "absent", check_only=True)
    assert not (root / "absent").exists()


@pytest.mark.parametrize(
    "name", ["../escape", "/absolute", "a/../../escape", "a\\evil"]
)
def test_manifest_paths_are_bounded(setup, name):
    root, lab = setup
    data = json.loads(m.MODEL_MANIFEST.read_text())
    data["files"][0]["path"] = name
    m.MODEL_MANIFEST.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unsafe"):
        m.prepare_models(root / "models", lab)


def test_manifest_duplicate_rejected(setup):
    root, lab = setup
    data = json.loads(m.MODEL_MANIFEST.read_text())
    data["files"].append(data["files"][0])
    m.MODEL_MANIFEST.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Invalid pinned"):
        m.prepare_models(root / "models", lab)


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_archive_links_and_special_members_rejected(setup, monkeypatch, kind):
    root, lab = setup
    source = lab / "source.tar.gz"
    archive(source, [("Sources/FluidAudio/evil", b"", kind)])
    monkeypatch.setattr(m, "SDK_BYTES", source.stat().st_size)
    monkeypatch.setattr(m, "SDK_SHA", m.digest(source))
    with pytest.raises(ValueError, match="forbidden"):
        m.extract_sdk(source, root / "sdk")


def test_sdk_hash_is_required_before_extraction(setup):
    root, lab = setup
    source = lab / "source.tar.gz"
    source.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="integrity"):
        m.extract_sdk(source, root / "sdk")
    assert not (root / "sdk").exists()


@pytest.mark.parametrize("location", ["destination", "parent", "asset", "manifest"])
def test_symlink_destination_and_assets_rejected(setup, location):
    root, lab = setup
    models = root / "models"
    if location == "destination":
        models.symlink_to(lab / "models", target_is_directory=True)
    elif location == "parent":
        parent = root / "linked"
        parent.symlink_to(lab, target_is_directory=True)
        models = parent / "target"
    else:
        m.prepare_models(models, lab)
        name = (
            "manifest.json"
            if location == "manifest"
            else "Synthetic.mlmodelc/weights.bin"
        )
        path = models / name
        original = root / "original"
        path.rename(original)
        path.symlink_to(original)
    with pytest.raises(ValueError, match="symlink"):
        m.prepare_models(models, lab)


def test_corrupt_existing_asset_not_overwritten(setup):
    root, lab = setup
    models = root / "models"
    m.prepare_models(models, lab)
    path = models / "Synthetic.mlmodelc/weights.bin"
    path.write_bytes(b"broken")
    with pytest.raises(ValueError, match="integrity"):
        m.prepare_models(models, lab)
    assert path.read_bytes() == b"broken"


def test_tampered_binary_and_resources_detected(setup):
    root, lab = setup
    tooling = root / "tooling"
    m.prepare_tooling(tooling, lab)
    (tooling / "memora-community").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        m.check_tooling(tooling)


def test_build_resource_changes_require_new_install(setup):
    root, lab = setup
    tooling = root / "tooling"
    m.prepare_tooling(tooling, lab)
    (m.RESOURCES / m.BUILD_RESOURCES[0]).write_text("changed")
    with pytest.raises(ValueError, match="provenance"):
        m.check_tooling(tooling)


def test_build_failure_does_not_publish_partial_tooling(setup, monkeypatch):
    root, lab = setup

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("swift", 900)

    monkeypatch.setattr(m.subprocess, "run", fail)
    with pytest.raises(ValueError, match="build failed"):
        m.prepare_tooling(root / "tooling", lab)
    assert not (root / "tooling").exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://huggingface.co/x",
        "https://evil.example/x",
        "https://user:secret@github.com/x",
        "https://github.com:444/x",
    ],
)
def test_download_hosts_and_scheme_restricted(url):
    with pytest.raises(ValueError, match="Untrusted"):
        m.check_url(url)


def test_https_redirect_stays_restricted():
    handler = m.Redirects()
    with pytest.raises(ValueError, match="Untrusted"):
        handler.redirect_request(None, None, 302, "", {}, "https://evil.example/weight")


def test_download_pinned_size_limit(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        pass

    class Opener:
        def open(self, *args, **kwargs):
            return Response(b"too many bytes")

    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(ValueError, match="exceeds"):
        m.download("https://huggingface.co/test", tmp_path / "download", 3, sha(b"abc"))
