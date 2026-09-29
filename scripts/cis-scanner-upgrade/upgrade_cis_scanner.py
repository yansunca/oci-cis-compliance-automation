#!/usr/bin/env python3
"""Build and publish a runner with a newer cis_reports.py. Does not deploy it.

Requires Python 3.9+, Docker logged in to OCIR, and a builder matching the image CPU.
  python3 scripts/cis-scanner-upgrade/upgrade_cis_scanner.py --current-image IMAGE \
    --output build/cis-upgrade [--version latest]

Saves new_image and previous_image in upgrade.json. Use the customer's existing
deployment method to select new_image, or previous_image for rollback.
No OCI configuration, infrastructure, or existing source files are changed.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "oci-landing-zones/oci-cis-landingzone-quickstart"


def run(*command, visible=False):
    result = subprocess.run(command, check=True, text=True, capture_output=not visible)
    return (result.stdout or "").strip()


def download(url):
    with urlopen(Request(url, headers={"User-Agent": "cis-scanner-upgrade"}), timeout=60) as response:
        return response.read()


def repository(image):
    match = re.fullmatch(r"([a-z0-9][a-z0-9.:-]*/[a-z0-9][a-z0-9._/-]*)"
                         r"(@sha256:[0-9a-f]{64}|:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})", image)
    if not match:
        raise ValueError("Provide a fully qualified registry image with a tag or digest.")
    return match[1]


def digest(image):
    info = json.loads(run("docker", "image", "inspect", image))[0]
    matches = {uri for uri in info.get("RepoDigests", []) if uri.startswith(repository(image) + "@sha256:")}
    if len(matches) != 1:
        raise ValueError("Could not resolve a unique image digest.")
    return matches.pop()


def build(args):
    # 1. Download a stable Oracle release at an exact source commit.
    if args.output.exists():
        raise ValueError("Use a new output directory; keep previous records for rollback.")
    if args.version != "latest" and not re.fullmatch(r"v?\d+\.\d+\.\d+", args.version):
        raise ValueError("Use latest or a stable release such as v3.4.2.")
    api = f"https://api.github.com/repos/{REPO}"
    release_path = "latest" if args.version == "latest" else "tags/v" + args.version.removeprefix("v")
    release = json.loads(download(f"{api}/releases/{release_path}"))
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
        raise ValueError("Expected a published stable release.")
    commit = json.loads(download(f"{api}/commits/{tag}"))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid source commit.")
    source = download(f"https://raw.githubusercontent.com/{REPO}/{commit}/scripts/cis_reports.py")
    checksum = hashlib.sha256(source).hexdigest()

    # 2. Reuse the existing runner image and its installed dependencies.
    image_repo = repository(args.current_image)
    run("docker", "pull", args.current_image, visible=True)
    previous = digest(args.current_image)
    new_tag = f"{image_repo}:cis-{tag.removeprefix('v')}-{uuid.uuid4().hex[:12]}"
    with tempfile.TemporaryDirectory(prefix="cis-build-") as folder:
        context = Path(folder)
        container = run("docker", "create", "--entrypoint", "python", previous, "--version")
        try:
            run("docker", "cp", f"{container}:/app/run_cis.py", str(context / "run_cis.py"))
        finally:
            run("docker", "rm", container)
        # The wrapper has a hardcoded report version; change that label only.
        wrapper = (context / "run_cis.py").read_bytes().decode("utf-8")
        wrapper, count = re.subn(r'("scannerVersion"\s*:\s*")[^"\n]+(")',
                                lambda m: m[1] + tag.removeprefix("v") + m[2], wrapper)
        if count != 1:
            raise ValueError("Could not find one scannerVersion label in the existing wrapper.")
        (context / "run_cis.py").write_bytes(wrapper.encode("utf-8"))
        (context / "cis_reports.py").write_bytes(source)
        (context / "Dockerfile").write_text(f"FROM {previous}\nCOPY cis_reports.py run_cis.py /app/\n")
        run("docker", "build", "-t", new_tag, folder, visible=True)
        # This catches missing imports, not live OCI or report-format incompatibilities.
        check = ("import sys, hashlib; from pathlib import Path; sys.path.insert(0, '/app'); "
                 "import run_cis; assert hashlib.sha256(Path('/app/cis_reports.py').read_bytes()).hexdigest() == sys.argv[1]")
        run("docker", "run", "--rm", "--network", "none", "--read-only", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "--entrypoint", "python", new_tag, "-c", check, checksum, visible=True)

        # 3. Publish under a new tag and retain the old immutable digest for rollback.
        args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
        run("docker", "push", new_tag, visible=True)
        record = {"previous_image": previous, "new_image": digest(new_tag),
                  "cis_version": tag, "source_commit": commit, "script_sha256": checksum}
        (args.output / "upgrade.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Image published; production unchanged. Record: {args.output / 'upgrade.json'}")
    print(f"New scanner: {record['new_image']}\nRollback image: {record['previous_image']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--current-image", required=True, help="Currently deployed runner image URI")
    parser.add_argument("--version", default="latest", help="Stable release tag, or latest (default)")
    parser.add_argument("--output", type=Path, required=True, help="New directory for upgrade.json")
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"ERROR: {error}")
