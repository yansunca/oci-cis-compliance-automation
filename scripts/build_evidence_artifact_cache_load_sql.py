#!/usr/bin/env python3
"""Build SQLcl load SQL for native CIS report artifact BLOBs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import mimetypes
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())

from scripts.build_adb_direct_load_sql import sql_literal


DEFAULT_RUN_ID = "FUNC-CIS-MAIN-20260722T073104Z"
DEFAULT_REPORT_DIR = Path(f"/private/tmp/oci-cis-native-converted-latest/{DEFAULT_RUN_ID}/reports")
DEFAULT_OUTPUT = Path("/private/tmp/oci-cis-evidence-artifact-cache-load.sql")
MAX_BASE64_CHUNK_CHARS = 30000


def build_sql(report_dir: Path, *, run_id: str, source_prefix: str = "reports") -> str:
    if not report_dir.is_dir():
        raise ValueError(f"report directory not found: {report_dir}")

    artifact_paths = sorted(path for path in report_dir.iterdir() if path.is_file())
    if not artifact_paths:
        raise ValueError(f"no report files found in {report_dir}")

    lines = [
        f"-- Evidence artifact cache load for {run_id}.",
        f"-- Source directory: {report_dir}",
        "set define off",
        "set sqlblanklines on",
        "whenever sqlerror exit sql.sqlcode rollback",
        "",
    ]
    for artifact_path in artifact_paths:
        lines.append(_artifact_load_block(artifact_path, run_id=run_id, source_prefix=source_prefix))

    lines.extend(
        [
            "COMMIT;",
            "",
            "SELECT artifact_role, COUNT(*) AS artifact_count",
            "FROM v_cis_evidence_artifact_downloads",
            f"WHERE run_id = {sql_literal(run_id)}",
            "GROUP BY artifact_role",
            "ORDER BY artifact_role;",
            "exit success",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_load_block(path: Path, *, run_id: str, source_prefix: str) -> str:
    content = path.read_bytes()
    mime_type = _mime_type(path)
    checksum = "sha256:" + hashlib.sha256(content).hexdigest()
    source_path = f"{source_prefix.rstrip('/')}/{path.name}"
    encoded = base64.b64encode(content).decode("ascii")
    chunks = [
        encoded[index : index + MAX_BASE64_CHUNK_CHARS]
        for index in range(0, len(encoded), MAX_BASE64_CHUNK_CHARS)
    ] or [""]

    lines = [
        f"prompt Loading evidence artifact {source_path}",
        "DECLARE",
        "    l_blob BLOB;",
        "    l_raw RAW(32767);",
        "BEGIN",
        "    DBMS_LOB.createtemporary(l_blob, TRUE);",
    ]
    for chunk in chunks:
        lines.extend(
            [
                f"    l_raw := UTL_ENCODE.base64_decode(UTL_RAW.cast_to_raw({sql_literal(chunk)}));",
                "    DBMS_LOB.writeappend(l_blob, UTL_RAW.length(l_raw), l_raw);",
            ]
        )
    lines.extend(
        [
            "    DELETE FROM cis_evidence_artifact_cache",
            f"    WHERE run_id = {sql_literal(run_id)}",
            f"    AND source_path = {sql_literal(source_path)};",
            "    INSERT INTO cis_evidence_artifact_cache (",
            "        run_id, source_path, artifact_file_name, mime_type, checksum,",
            "        size_bytes, content_blob, status, updated_at",
            "    ) VALUES (",
            f"        {sql_literal(run_id)},",
            f"        {sql_literal(source_path)},",
            f"        {sql_literal(path.name)},",
            f"        {sql_literal(mime_type)},",
            f"        {sql_literal(checksum)},",
            f"        {len(content)},",
            "        l_blob,",
            "        'ACTIVE',",
            "        SYSTIMESTAMP",
            "    );",
            "    DBMS_LOB.freetemporary(l_blob);",
            "END;",
            "/",
            "",
        ]
    )
    return "\n".join(lines)


def _mime_type(path: Path) -> str:
    if path.suffix.lower() == ".jsonl":
        return "application/x-ndjson"
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR, type=Path)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--source-prefix", default="reports")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    args = parser.parse_args(argv)

    sql = build_sql(args.report_dir, run_id=args.run_id, source_prefix=args.source_prefix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sql, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
