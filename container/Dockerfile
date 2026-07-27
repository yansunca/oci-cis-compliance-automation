FROM python:3.11-slim

ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=8

ARG CIS_SCRIPT_REF=bc8301a97b25dcef251e9f91042e4c8bea2c7bb6
ARG CIS_SCRIPT_SHA256=402652611432c14a48397798f9c94414b4a07ab3c5916025589fbb7bf6ae74ee

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

# Oracle's script is the same file linked by the blog, pinned to a reviewed commit and checksum.
RUN python - <<'PY'
import hashlib
import os
import sys
from pathlib import Path
from urllib.request import urlopen

ref = os.environ.get("CIS_SCRIPT_REF", "bc8301a97b25dcef251e9f91042e4c8bea2c7bb6")
expected = os.environ.get("CIS_SCRIPT_SHA256", "402652611432c14a48397798f9c94414b4a07ab3c5916025589fbb7bf6ae74ee")
url = f"https://raw.githubusercontent.com/oci-landing-zones/oci-cis-landingzone-quickstart/{ref}/scripts/cis_reports.py"
content = urlopen(url, timeout=120).read()
actual = hashlib.sha256(content).hexdigest()
if actual != expected:
    print(f"cis_reports.py sha256 mismatch: expected {expected}, got {actual}", file=sys.stderr)
    raise SystemExit(1)
Path("/app/cis_reports.py").write_bytes(content)
PY

COPY run_cis.py .
CMD ["python", "run_cis.py"]
