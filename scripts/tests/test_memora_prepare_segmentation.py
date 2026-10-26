"""Disposable tiny archives only; no network or active model modifications."""

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "memora-prepare-segmentation.py"
spec = importlib.util.spec_from_file_location("prepare_segmentation_test", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
PAYLOAD = b"synthetic ONNX fixture"
LICENSE = b"MIT License\nCopyright synthetic authors\n"


def make_archive(path, extras=(), model_type=tarfile.REGTYPE):
    with tarfile.open(path, "w:bz2") as target:
        for name, content, kind in [
            (m.PREFIX + "model.onnx", PAYLOAD, model_type),
            (m.PREFIX + "LICENSE", LICENSE, tarfile.REGTYPE),
            *extras,
        ]:
            entry = tarfile.TarInfo(name)
            entry.type = kind
            entry.size = len(content) if kind == tarfile.REGTYPE else 0
            entry.linkname = "../../outside"
            target.addfile(entry, io.BytesIO(content) if entry.isfile() else None)
    return path


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    source = make_archive(tmp_path / "source.tar.bz2")
    monkeypatch.setattr(
        m, "LICENSE_SHA", hashlib.sha256(LICENSE).hexdigest(), raising=False
    )
    monkeypatch.setattr(m, "MODEL_BYTES", len(PAYLOAD))
    monkeypatch.setattr(m, "MODEL_SHA", hashlib.sha256(PAYLOAD).hexdigest())

    def pin(path):
        monkeypatch.setattr(m, "ARCHIVE_BYTES", path.stat().st_size)
        monkeypatch.setattr(
            m, "ARCHIVE_SHA", hashlib.sha256(path.read_bytes()).hexdigest()
        )

    pin(source)
    return tmp_path / "models/segmentation", source, pin


def test_local_archive_install_then_check_is_offline_and_idempotent(prepared):
    folder, archive, _ = prepared
    with patch.object(
        m.urllib.request, "urlopen", side_effect=AssertionError("No network")
    ):
        m.prepare(folder, archive)
        before = {
            p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.iterdir()
        }
        m.prepare(folder)
        m.prepare(folder, check_only=True)
    after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.iterdir()}
    assert after == before
    assert (folder / "model.onnx").read_bytes() == PAYLOAD
    assert (folder / "LICENSE").read_bytes() == LICENSE
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["license"] == "MIT" and manifest["sha256"] == m.MODEL_SHA


def test_check_missing_is_readonly(prepared):
    folder, _, _ = prepared
    with patch.object(
        m.urllib.request, "urlopen", side_effect=AssertionError("No network")
    ):
        with pytest.raises(ValueError, match="not prepared"):
            m.prepare(folder, check_only=True)
    assert not folder.parent.exists()


def test_corrupt_installed_model_never_repaired(prepared):
    folder, archive, _ = prepared
    m.prepare(folder, archive)
    damaged = b"X" + PAYLOAD[1:]
    (folder / "model.onnx").write_bytes(damaged)
    with patch.object(
        m.urllib.request, "urlopen", side_effect=AssertionError("No network")
    ):
        with pytest.raises(ValueError, match="SHA256"):
            m.prepare(folder)
    assert (folder / "model.onnx").read_bytes() == damaged


def test_corrupt_input_never_publishes_partial_model(prepared):
    folder, archive, _ = prepared
    archive.write_bytes(b"bad")
    with pytest.raises(ValueError, match="size"):
        m.prepare(folder, archive)
    assert not folder.exists()
    assert not list(folder.parent.glob(".segmentation-*"))


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_model_link_members_rejected(prepared, kind):
    folder, archive, pin = prepared
    make_archive(archive, model_type=kind)
    pin(archive)
    with pytest.raises(ValueError, match="archive member"):
        m.prepare(folder, archive)
    assert not folder.exists()
    assert not (folder.parent / "outside").exists()


def test_arbitrary_and_traversal_members_are_not_extracted(prepared):
    folder, archive, pin = prepared
    make_archive(
        archive,
        extras=[
            ("../../outside", b"never extracted", tarfile.REGTYPE),
            ("/absolute-unrelated", b"never extracted", tarfile.REGTYPE),
            (m.PREFIX + "foreign-link", b"", tarfile.SYMTYPE),
        ],
    )
    pin(archive)
    m.prepare(folder, archive)
    assert {p.name for p in folder.iterdir()} == {
        "model.onnx",
        "LICENSE",
        "NOTICE.md",
        "manifest.json",
    }
    assert not (archive.parent / "outside").exists()
    assert not any(p.is_symlink() for p in folder.iterdir())


def test_duplicate_model_is_rejected(prepared):
    folder, archive, pin = prepared
    make_archive(archive, extras=[(m.PREFIX + "model.onnx", PAYLOAD, tarfile.REGTYPE)])
    pin(archive)
    with pytest.raises(ValueError, match="archive member"):
        m.prepare(folder, archive)
    assert not folder.exists()


def test_download_pinned_success(prepared):
    folder, archive, _ = prepared
    with patch.object(
        m.urllib.request, "urlopen", return_value=io.BytesIO(archive.read_bytes())
    ) as request:
        m.prepare(folder)
    request.assert_called_once_with(m.SOURCE, timeout=60)
    assert (folder / "model.onnx").read_bytes() == PAYLOAD


def test_download_is_size_bounded_and_temporary_files_removed(prepared):
    folder, _, _ = prepared
    with patch.object(
        m.urllib.request,
        "urlopen",
        return_value=io.BytesIO(b"X" * (m.ARCHIVE_BYTES + 1)),
    ):
        with pytest.raises(ValueError, match="exceeds"):
            m.prepare(folder)
    assert not folder.exists()
    assert not list(folder.parent.glob(".segmentation-*"))


def test_concurrent_install_never_overwrites_new_destination(prepared):
    folder, archive, _ = prepared
    original = m.shutil.copyfileobj
    created = False

    def copy_and_race(source, target):
        nonlocal created
        original(source, target)
        if not created:
            created = True
            folder.mkdir()
            (folder / "sentinel").write_text("existing concurrent installation")

    with patch.object(m.shutil, "copyfileobj", side_effect=copy_and_race):
        with pytest.raises(ValueError, match="Concurrent"):
            m.prepare(folder, archive)
    assert (folder / "sentinel").read_text() == "existing concurrent installation"
    assert list(folder.iterdir()) == [folder / "sentinel"]


def test_destination_symlink_rejected(prepared, tmp_path):
    folder, archive, _ = prepared
    folder.parent.mkdir()
    target = tmp_path / "untouched"
    target.mkdir()
    folder.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        m.prepare(folder, archive)
    assert list(target.iterdir()) == []


def test_installed_manifest_symlink_rejected(prepared, tmp_path):
    folder, archive, _ = prepared
    m.prepare(folder, archive)
    manifest = folder / "manifest.json"
    outside = tmp_path / "external-manifest.json"
    outside.write_bytes(manifest.read_bytes())
    manifest.unlink()
    manifest.symlink_to(outside)
    with pytest.raises(ValueError, match="[Ss]ymlink|manifest"):
        m.prepare(folder, check_only=True)
    assert manifest.is_symlink()


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_installed_license_required_and_verified(prepared, damage):
    folder, archive, _ = prepared
    m.prepare(folder, archive)
    license_file = folder / "LICENSE"
    if damage == "missing":
        license_file.unlink()
    else:
        license_file.write_bytes(LICENSE.replace(b"authors", b"xxxxxxx"))
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    with patch.object(
        m.urllib.request, "urlopen", side_effect=AssertionError("No network")
    ):
        with pytest.raises(ValueError):
            m.prepare(folder, check_only=True)
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}
