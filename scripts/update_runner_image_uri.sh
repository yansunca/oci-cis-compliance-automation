#!/usr/bin/env bash
set -euo pipefail

TFVARS_FILE="${TFVARS_FILE:-terraform.tfvars}"
RUNNER_IMAGE_URI="${RUNNER_IMAGE_URI:-}"

if [ ! -f "$TFVARS_FILE" ]; then
  echo "ERROR: $TFVARS_FILE was not found. Copy terraform.tfvars.example first." >&2
  exit 2
fi

if [ -z "$RUNNER_IMAGE_URI" ]; then
  RUNNER_IMAGE_URI="$(scripts/print_runner_image_digest.sh)"
fi

export TFVARS_FILE RUNNER_IMAGE_URI
python3 - <<'PY'
from pathlib import Path
import os
import re

path = Path(os.environ["TFVARS_FILE"])
uri = os.environ["RUNNER_IMAGE_URI"].strip()
if not uri:
    raise SystemExit("RUNNER_IMAGE_URI is empty")
if "@sha256:" not in uri:
    raise SystemExit(f"RUNNER_IMAGE_URI must be a digest URI with @sha256: {uri}")

text = path.read_text()
line = f'runner_image_uri = "{uri}"'
pattern = re.compile(r'(?m)^\s*#?\s*runner_image_uri\s*=\s*"[^"]*"\s*$')
if pattern.search(text):
    text = pattern.sub(line, text, count=1)
else:
    marker = "# Scanner output and evidence options."
    if marker in text:
        text = text.replace(marker, f"# Digest-pinned runner image.\n{line}\n\n{marker}", 1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\n# Digest-pinned runner image.\n{line}\n"
path.write_text(text)
print(line)
PY
