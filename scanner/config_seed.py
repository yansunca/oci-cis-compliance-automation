"""Export source-profile configuration seed files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scanner.source_contract import SOURCE_PROFILES


CONFIG_VERSION_ID = "source-contract-v1"


@dataclass(frozen=True)
class ConfigSeedFiles:
    """Paths for generated configuration seed JSONL files."""

    config_version: Path
    source_profile: Path
    field_alias: Path

    @property
    def paths(self) -> tuple[Path, Path, Path]:
        return (self.config_version, self.source_profile, self.field_alias)


def write_config_seed(config_dir: Path) -> ConfigSeedFiles:
    """Write JSONL seed files for config tables in the initial migration."""

    config_dir.mkdir(parents=True, exist_ok=True)
    files = ConfigSeedFiles(
        config_version=config_dir / "config_version.jsonl",
        source_profile=config_dir / "source_profile.jsonl",
        field_alias=config_dir / "field_alias.jsonl",
    )
    _write_jsonl(
        files.config_version,
        [
            {
                "config_version_id": CONFIG_VERSION_ID,
                "status": "ACTIVE",
                "description": "Initial source contract profile configuration.",
            },
        ],
    )
    _write_jsonl(
        files.source_profile,
        [
            {
                "source_profile_id": profile.profile_id,
                "config_version_id": CONFIG_VERSION_ID,
                "display_name": profile.display_name,
                "schema_hash": profile.schema_hash,
                "required_headers_json": json.dumps(list(profile.required_headers)),
            }
            for profile in sorted(SOURCE_PROFILES.values(), key=lambda item: item.profile_id)
        ],
    )
    alias_rows = []
    for profile in sorted(SOURCE_PROFILES.values(), key=lambda item: item.profile_id):
        for source_header, canonical_header in sorted(profile.aliases.items()):
            alias_rows.append(
                {
                    "source_profile_id": profile.profile_id,
                    "config_version_id": CONFIG_VERSION_ID,
                    "source_header": source_header,
                    "canonical_header": canonical_header,
                },
            )
    _write_jsonl(files.field_alias, alias_rows)
    return files


def _write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
