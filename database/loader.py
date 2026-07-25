"""Local load-plan builder for ADB staging ingestion.

This module intentionally does not connect to Autonomous Database. It consumes
validated wrapper output and returns the ordered files, row counts, and
idempotency keys a future ADB loader must honor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanner.staging_validator import StagingValidationResult, validate_staging_run


@dataclass(frozen=True)
class LoadStep:
    """One ordered file-to-table load operation."""

    table_name: str
    relative_path: str
    row_count: int
    idempotency_key: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    lookup_key: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadPlan:
    """Validated local ADB load plan for one wrapper run."""

    run_dir: Path
    validation: StagingValidationResult
    steps: tuple[LoadStep, ...]

    @property
    def total_rows(self) -> int:
        """Total rows expected across all staged table loads."""

        return sum(step.row_count for step in self.steps)

    @property
    def table_order(self) -> tuple[str, ...]:
        """Ordered table names for loader execution."""

        return tuple(step.table_name for step in self.steps)


class LoadPlanError(ValueError):
    """Raised when wrapper output is not eligible for database loading."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("staging run is not load-ready: " + "; ".join(errors))


def build_load_plan(run_dir: Path) -> LoadPlan:
    """Build an ordered load plan after dry-run validation succeeds."""

    validation = validate_staging_run(run_dir)
    if not validation.is_valid:
        raise LoadPlanError(validation.errors)

    return LoadPlan(
        run_dir=run_dir,
        validation=validation,
        steps=(
            LoadStep(
                table_name="scan_run",
                relative_path="staging/scan_run.jsonl",
                row_count=validation.counts["scan_run"],
                idempotency_key=("run_id",),
            ),
            LoadStep(
                table_name="scan_file",
                relative_path="staging/scan_file.jsonl",
                row_count=validation.counts["scan_file"],
                idempotency_key=("run_id", "source_path"),
                depends_on=("scan_run",),
            ),
            LoadStep(
                table_name="config_version",
                relative_path="config/config_version.jsonl",
                row_count=validation.counts["config_version"],
                idempotency_key=("config_version_id",),
            ),
            LoadStep(
                table_name="source_profile",
                relative_path="config/source_profile.jsonl",
                row_count=validation.counts["source_profile"],
                idempotency_key=("source_profile_id", "config_version_id"),
                depends_on=("config_version",),
            ),
            LoadStep(
                table_name="field_alias",
                relative_path="config/field_alias.jsonl",
                row_count=validation.counts["field_alias"],
                idempotency_key=("source_profile_id", "config_version_id", "source_header"),
                depends_on=("source_profile",),
            ),
            LoadStep(
                table_name="raw_cis_record",
                relative_path="raw/records-00001.jsonl",
                row_count=validation.counts["raw_cis_record"],
                idempotency_key=("run_id", "scan_file_id", "source_row"),
                depends_on=("scan_run", "scan_file"),
                lookup_key=("run_id", "scan_file_path"),
            ),
            LoadStep(
                table_name="canonical_finding_stage",
                relative_path="staging/canonical_finding_stage.jsonl",
                row_count=validation.counts["canonical_finding_stage"],
                idempotency_key=("run_id", "finding_id", "source_file", "source_row"),
                depends_on=("scan_run",),
            ),
        ),
    )
