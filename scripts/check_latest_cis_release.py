#!/usr/bin/env python3
"""Print latest stable OCI CIS script release metadata from GitHub.

This is intentionally read-only. Use it in CI to detect that the pinned scanner
image source should be reviewed, smoke-tested, and promoted.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request

REPO_API = "https://api.github.com/repos/oci-landing-zones/oci-cis-landingzone-quickstart/releases/latest"
RAW_URL_TEMPLATE = "https://raw.githubusercontent.com/oci-landing-zones/oci-cis-landingzone-quickstart/{tag}/scripts/cis_reports.py"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "oci-cis-release-checker"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "oci-cis-release-checker"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def main() -> int:
    release = fetch_json(REPO_API)
    tag = release["tag_name"]
    script_url = RAW_URL_TEMPLATE.format(tag=tag)
    script = fetch_bytes(script_url)
    result = {
        "LATEST_VERSION": tag.lstrip("v"),
        "latestTag": tag,
        "publishedAt": release.get("published_at"),
        "scriptUrl": script_url,
        "scriptSha256": hashlib.sha256(script).hexdigest(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
