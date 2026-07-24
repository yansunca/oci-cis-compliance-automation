# Scanner

Scanner utilities convert real `cis_reports.py` output into the operational package consumed by
Object Storage, Autonomous Database, APEX, OAC, and Log Analytics.

Current modules:

- `native_report_converter.py`: converts a real CIS report folder into landing, raw, canonical, staging, manifest, and readiness artifacts.
- `cli.py`: local CLI. Current command: `native-report-run`.
- `source_contract.py`: source profiles, normalized schema hashes, aliases, and compatibility rules.
- `landing.py`: streaming CSV-to-landing JSONL conversion.
- `normalizer.py`: canonical finding normalizer and stable finding fingerprint helper.
- `evidence.py`: checksums, file manifest entries, manifest, and run-ready helpers.
- `staging_export.py`: scan-run and scan-file JSONL export derived from manifest data.
- `staging_validator.py`: dry-run validation for generated run packages before database loading.
- `config_seed.py`: source profile, alias, and config version seed export.
- `operational_log.py`: safe structured log event envelope.
- `source_package.py`: pinned source release, commit, and script checksum verification.
- `runtime_config.py`, `process_runner.py`, and `run_layout.py`: runtime parsing, subprocess capture, and deterministic run layout.

Example conversion of real CIS report files:

```bash
python -m scanner.cli native-report-run \
  --native-report-dir /tmp/FUNC-CIS-20260722T120000Z/files \
  --output-root /tmp/oci-cis-converted \
  --run-id FUNC-CIS-20260722T120000Z \
  --tenancy-id ocid1.tenancy.oc1..example \
  --scanner-version 3.3.0
```

The generated run package uses:

- `files/` for original CIS HTML/CSV/JSON/log evidence.
- `manifest.json` and `run_ready.json` for completeness and load gating.
- `_SUCCESS.txt` as the preferred completion marker.
- `landing/`, `raw/`, `canonical/`, `staging/`, `config/`, and `logs/` for ADB loading and observability.

No committed sample scan data is required or expected.
