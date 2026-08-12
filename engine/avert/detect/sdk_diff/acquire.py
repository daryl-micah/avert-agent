from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


def download_artifact(*, ecosystem: str, package: str, version: str, destination: Path) -> Path:
    """Downloads and expands one published SDK into a caller-owned temp directory."""
    destination.mkdir(parents=True, exist_ok=True)
    if ecosystem == "pypi":
        subprocess.run(
            [sys.executable, "-m", "pip", "download", "--no-deps", "--dest", str(destination), f"{package}=={version}"],
            check=True,
        )
        archive = next(destination.glob("*.whl"), None) or next(destination.glob("*.tar.gz"))
        extracted = destination / "artifact"
        if archive.suffix == ".whl":
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(extracted)
        else:
            with tarfile.open(archive) as tf:
                tf.extractall(extracted, filter="data")
        return extracted
    if ecosystem == "npm":
        subprocess.run(["npm", "pack", f"{package}@{version}", "--pack-destination", str(destination)], check=True)
        archive = next(destination.glob("*.tgz"))
        extracted = destination / "artifact"
        with tarfile.open(archive) as tf:
            tf.extractall(extracted, filter="data")
        return extracted / "package"
    raise ValueError(f"unsupported ecosystem: {ecosystem}")


def downloaded_pair(*, ecosystem: str, package: str, from_version: str, to_version: str):
    tempdir = tempfile.TemporaryDirectory(prefix="avert-sdk-diff-")
    root = Path(tempdir.name)
    return tempdir, (
        download_artifact(ecosystem=ecosystem, package=package, version=from_version, destination=root / "from"),
        download_artifact(ecosystem=ecosystem, package=package, version=to_version, destination=root / "to"),
    )
