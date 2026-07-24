"""Deterministic local run-directory layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunLayout:
    """Filesystem layout for one scanner wrapper run."""

    run_dir: Path
    reports_dir: Path
    landing_dir: Path
    raw_dir: Path
    canonical_dir: Path
    staging_dir: Path
    config_dir: Path
    logs_dir: Path
    manifest_path: Path
    run_ready_path: Path
    success_marker: Path
    failed_marker: Path


def build_run_layout(root: Path, run_id: str) -> RunLayout:
    """Create and return deterministic directories for one run."""

    run_dir = root / run_id
    reports_dir = run_dir / "reports"
    landing_dir = run_dir / "landing"
    raw_dir = run_dir / "raw"
    canonical_dir = run_dir / "canonical"
    staging_dir = run_dir / "staging"
    config_dir = run_dir / "config"
    logs_dir = run_dir / "logs"
    for directory in (
        reports_dir,
        landing_dir,
        raw_dir,
        canonical_dir,
        staging_dir,
        config_dir,
        logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return RunLayout(
        run_dir=run_dir,
        reports_dir=reports_dir,
        landing_dir=landing_dir,
        raw_dir=raw_dir,
        canonical_dir=canonical_dir,
        staging_dir=staging_dir,
        config_dir=config_dir,
        logs_dir=logs_dir,
        manifest_path=run_dir / "manifest.json",
        run_ready_path=run_dir / "run_ready.json",
        success_marker=run_dir / "_SUCCESS",
        failed_marker=run_dir / "_FAILED",
    )
