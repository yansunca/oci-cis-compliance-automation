"""Pinned source-package verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanner.evidence import sha256_file


@dataclass(frozen=True)
class SourcePackageIdentity:
    """Expected identity for a pinned upstream CIS source package."""

    release_tag: str
    commit: str
    script_sha256: str


@dataclass(frozen=True)
class SourcePackageVerification:
    """Observed source-package identity after verification."""

    release_tag: str
    commit: str
    script_path: Path
    script_sha256: str


def verify_source_package(
    *,
    source_root: Path,
    script_relative_path: str,
    actual_release_tag: str,
    actual_commit: str,
    expected: SourcePackageIdentity,
) -> SourcePackageVerification:
    """Verify release tag, commit, and script checksum for a local source tree."""

    if actual_release_tag != expected.release_tag:
        raise ValueError(
            f"source release mismatch: expected {expected.release_tag}, got {actual_release_tag}",
        )
    if actual_commit != expected.commit:
        raise ValueError(f"source commit mismatch: expected {expected.commit}, got {actual_commit}")

    script_path = source_root / script_relative_path
    if not script_path.is_file():
        raise ValueError(f"source script not found: {script_path}")
    script_sha256 = sha256_file(script_path)
    if script_sha256 != expected.script_sha256:
        raise ValueError(
            f"script checksum mismatch: expected {expected.script_sha256}, got {script_sha256}",
        )

    return SourcePackageVerification(
        release_tag=actual_release_tag,
        commit=actual_commit,
        script_path=script_path,
        script_sha256=script_sha256,
    )
