"""Adversarial tests for the retained OCI Python-image manifest."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest

from kernel import config as kernel_config
from kernel.runtime_bundle import _validate_runtime_image_manifest
from tooling import runtime_image_manifest as image_manifest


def _layer(path: Path, members: dict[str, bytes]) -> tuple[str, int, str]:
    with tarfile.open(path, "w:gz") as archive:
        for name, value in members.items():
            info = tarfile.TarInfo(name)
            info.mode = 0o755 if name.endswith(("python3.12", "/git")) else 0o644
            info.size = len(value)
            archive.addfile(info, io.BytesIO(value))
    raw = path.read_bytes()
    expanded = gzip.decompress(raw)
    return (
        "sha256:" + hashlib.sha256(raw).hexdigest(),
        len(raw),
        "sha256:" + hashlib.sha256(expanded).hexdigest(),
    )


def _write_json(path: Path, value: dict) -> tuple[str, int]:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return "sha256:" + hashlib.sha256(raw).hexdigest(), len(raw)


def _synthetic_oci(tmp_path: Path, monkeypatch):
    first = tmp_path / "layer-1.tar.gz"
    second = tmp_path / "layer-2.tar.gz"
    layer_one = _layer(first, {
        "usr/local/lib/python3.12/base.py": b"lower layer\n",
        "usr/local/lib/python3.12/old.py": b"must disappear\n",
        "usr/local/lib/python3.12/opaque/lower.py": b"must disappear\n",
        "usr/local/bin/python3.12": b"synthetic python executable\n",
        "usr/local/lib/libpython3.12.so.1.0": b"synthetic libpython\n",
        "usr/lib/libc.so.6": b"synthetic libc\n",
        "usr/lib/python3/dist-packages/z-native.so": b"synthetic native z\n",
        "usr/lib/python3.11/lib-dynload/a-native.so": b"synthetic native a\n",
        "usr/bin/git": b"synthetic git\n",
        "etc/ld.so.cache": b"synthetic cache\n",
        "etc/ld.so.conf": b"include /etc/ld.so.conf.d/*.conf\n",
    })
    layer_two = _layer(second, {
        "usr/local/lib/python3.12/.wh.old.py": b"",
        "usr/local/lib/python3.12/base.py": b"upper layer\n",
        "usr/local/lib/python3.12/opaque/.wh..wh..opq": b"",
        "usr/local/lib/python3.12/opaque/upper.py": b"retained\n",
    })
    config_path = tmp_path / "config.json"
    config = {
        "architecture": "amd64",
        "os": "linux",
        "config": {"Env": ["PYTHON_VERSION=3.12.13"]},
        "rootfs": {"diff_ids": [layer_one[2], layer_two[2]]},
    }
    config_digest, config_length = _write_json(config_path, config)
    platform_path = tmp_path / "platform.json"
    platform_document = {
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": config_digest,
            "size": config_length,
        },
        "layers": [{
            "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
            "digest": digest,
            "size": length,
        } for digest, length, _diff_id in (layer_one, layer_two)],
    }
    platform_digest, _platform_length = _write_json(
        platform_path, platform_document)
    index_path = tmp_path / "index.json"
    index_document = {
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [{
            "digest": platform_digest,
            "platform": {"architecture": "amd64", "os": "linux"},
        }],
    }
    index_digest, _index_length = _write_json(index_path, index_document)
    monkeypatch.setattr(image_manifest, "IMAGE_INDEX_DIGEST", index_digest)
    monkeypatch.setattr(
        image_manifest, "PLATFORM_MANIFEST_DIGEST", platform_digest)
    return index_path, platform_path, config_path, [first, second]


def test_generator_derives_closed_tree_from_verified_oci_layers(
        tmp_path, monkeypatch):
    index, platform, config, layers = _synthetic_oci(tmp_path, monkeypatch)
    document = image_manifest.build_manifest(index, platform, config, layers)
    files = {
        entry["relativePath"]: entry
        for entry in document["python"]["standardLibraryRoots"][0]["files"]
    }
    assert "old.py" not in files
    assert "opaque/lower.py" not in files
    assert "opaque/upper.py" in files
    assert files["base.py"]["contentDigest"] == (
        "sha256:" + hashlib.sha256(b"upper layer\n").hexdigest())
    assert document["python"]["requiredAbsentPaths"] == ["/etc/ld.so.preload"]
    native_paths = [entry["path"] for entry in document["python"]["nativeFiles"]]
    assert native_paths == sorted(native_paths)


def test_committed_runtime_image_manifest_passes_runtime_validation():
    document = json.loads(
        (kernel_config.PACKAGE_ROOT / "conformance" /
         "python_runtime_image_manifest.json").read_text(encoding="utf-8"))
    _validate_runtime_image_manifest(document)


def test_generator_rejects_wrong_uncompressed_layer_identity(
        tmp_path, monkeypatch):
    index, platform, config, layers = _synthetic_oci(tmp_path, monkeypatch)
    config_document = json.loads(config.read_text(encoding="utf-8"))
    config_document["rootfs"]["diff_ids"][1] = "sha256:" + "0" * 64
    config_digest, config_length = _write_json(config, config_document)
    platform_document = json.loads(platform.read_text(encoding="utf-8"))
    platform_document["config"]["digest"] = config_digest
    platform_document["config"]["size"] = config_length
    platform_digest, _ = _write_json(platform, platform_document)
    index_document = json.loads(index.read_text(encoding="utf-8"))
    index_document["manifests"][0]["digest"] = platform_digest
    index_digest, _ = _write_json(index, index_document)
    monkeypatch.setattr(image_manifest, "IMAGE_INDEX_DIGEST", index_digest)
    monkeypatch.setattr(
        image_manifest, "PLATFORM_MANIFEST_DIGEST", platform_digest)
    with pytest.raises(image_manifest.ManifestError, match="layer"):
        image_manifest.build_manifest(index, platform, config, layers)


def test_layer_application_rejects_path_escape(tmp_path):
    layer = tmp_path / "unsafe.tar.gz"
    _layer(layer, {"../outside": b"hostile"})
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(image_manifest.ManifestError, match="unsafe path"):
        image_manifest._apply_layer(root, layer)
    assert not (tmp_path / "outside").exists()


def test_layer_application_rejects_symlink_and_hardlink_escape(tmp_path):
    for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
        layer = tmp_path / f"unsafe-{kind!r}.tar.gz"
        with tarfile.open(layer, "w:gz") as archive:
            link = tarfile.TarInfo("nested/escape")
            link.type = kind
            link.linkname = "../../outside"
            archive.addfile(link)
        root = tmp_path / f"root-{kind!r}"
        root.mkdir()
        with pytest.raises(image_manifest.ManifestError, match="escape|unsafe"):
            image_manifest._apply_layer(root, layer)
        assert not (tmp_path / "outside").exists()


def test_layer_application_supports_file_to_directory_replacement(tmp_path):
    lower = tmp_path / "lower.tar.gz"
    upper = tmp_path / "upper.tar.gz"
    _layer(lower, {"node": b"lower file"})
    with tarfile.open(upper, "w:gz") as archive:
        directory = tarfile.TarInfo("node")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        child = tarfile.TarInfo("node/child")
        child.size = len(b"upper file")
        archive.addfile(child, io.BytesIO(b"upper file"))
    root = tmp_path / "root-replacement"
    root.mkdir()
    image_manifest._apply_layer(root, lower)
    image_manifest._apply_layer(root, upper)
    assert (root / "node" / "child").read_bytes() == b"upper file"


@pytest.mark.parametrize("name", [".wh..", ".wh..."])
def test_layer_application_rejects_unsafe_whiteout(tmp_path, name):
    layer = tmp_path / "unsafe-whiteout.tar.gz"
    _layer(layer, {name: b""})
    outside = tmp_path / "outside-marker"
    outside.write_text("must survive", encoding="utf-8")
    root = tmp_path / "root-whiteout"
    root.mkdir()
    with pytest.raises(image_manifest.ManifestError, match="unsafe whiteout"):
        image_manifest._apply_layer(root, layer)
    assert outside.read_text(encoding="utf-8") == "must survive"


def test_layer_application_rejects_unsupported_member_type(tmp_path):
    layer = tmp_path / "unsupported.tar.gz"
    with tarfile.open(layer, "w:gz") as archive:
        fifo = tarfile.TarInfo("runtime-fifo")
        fifo.type = tarfile.FIFOTYPE
        archive.addfile(fifo)
    root = tmp_path / "root-unsupported"
    root.mkdir()
    with pytest.raises(image_manifest.ManifestError, match="unsupported member"):
        image_manifest._apply_layer(root, layer)


def test_deferred_hardlink_cannot_follow_later_symlink_outside_root(tmp_path):
    layer = tmp_path / "hardlink-order.tar.gz"
    outside = tmp_path / "outside-hardlink"
    outside.mkdir()
    with tarfile.open(layer, "w:gz") as archive:
        source = tarfile.TarInfo("source")
        source.size = len(b"retained")
        archive.addfile(source, io.BytesIO(b"retained"))
        hardlink = tarfile.TarInfo("a/link")
        hardlink.type = tarfile.LNKTYPE
        hardlink.linkname = "source"
        archive.addfile(hardlink)
        symlink = tarfile.TarInfo("a")
        symlink.type = tarfile.SYMTYPE
        symlink.linkname = str(outside)
        archive.addfile(symlink)
    root = tmp_path / "root-hardlink"
    root.mkdir()
    image_manifest._apply_layer(root, layer)
    assert list(outside.iterdir()) == []
