"""Decide whether to publish the package to a given target registry.

Publish (exit 0) when the current version (from pyproject.toml) is not
already present on the target registry.  Skip (exit 1) otherwise.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tomllib
import urllib.parse
import urllib.request


def _load_pyproject() -> dict:
    return tomllib.loads(
        pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    )


def get_current_version() -> str:
    """Read the version from pyproject.toml.

    Returns:
        The version string, e.g. ``"0.2.0"``.
    """
    return _load_pyproject()["project"]["version"]


def get_package_name() -> str:
    """Read the package name from pyproject.toml.

    Returns:
        The package name, e.g. ``"pylint-google-style"``.
    """
    return _load_pyproject()["project"]["name"]


def published_versions_gitlab() -> set[str]:
    """List all versions of the package on the GitLab Package Registry.

    Returns:
        Set of version strings already published.
    """
    api_url = os.environ["CI_API_V4_URL"]
    project_id = os.environ["CI_PROJECT_ID"]
    token = os.environ["CI_JOB_TOKEN"]
    name = get_package_name()

    url = (
        f"{api_url}/projects/{project_id}"
        f"/packages?package_type=pypi&package_name={urllib.parse.quote(name)}"
        f"&per_page=100"
    )
    req = urllib.request.Request(url, headers={"JOB-TOKEN": token})
    with urllib.request.urlopen(req) as resp:
        packages = json.loads(resp.read())
    return {p["version"] for p in packages if p.get("name") == name}


def published_versions_gcp() -> set[str]:
    """List all versions of the package on GCP Artifact Registry.

    Returns:
        Set of version strings already published.  Empty set when the
        package does not yet exist on the registry.
    """
    project = os.environ["GCP_AR_PROJECT"]
    location = os.environ["GCP_LOCATION"]
    repo = os.environ["GCP_REPO"]
    name = get_package_name()

    result = subprocess.run(
        [
            "gcloud",
            "artifacts",
            "versions",
            "list",
            f"--project={project}",
            f"--location={location}",
            f"--repository={repo}",
            f"--package={name}",
            "--format=value(name)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    # Each line is the full resource path; the version is the basename.
    return {
        line.rsplit("/", 1)[-1]
        for line in result.stdout.strip().splitlines()
        if line
    }


def published_versions(target: str) -> set[str]:
    """Dispatch to the registry-specific version listing.

    Args:
        target: ``"gitlab"`` or ``"gcp"``.

    Returns:
        Set of version strings already published on the target.
    """
    if target == "gitlab":
        return published_versions_gitlab()
    if target == "gcp":
        return published_versions_gcp()
    raise ValueError(f"Unknown target: {target}")


def main() -> None:
    """Decide whether to publish the current version to the given target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=["gitlab", "gcp"],
        required=True,
        help="Registry to check.",
    )
    args = parser.parse_args()

    current = get_current_version()
    tag = f"[{args.target}]"
    versions = published_versions(args.target)

    if current in versions:
        print(f"{tag} {current} already published, skipping.")
        sys.exit(1)

    print(f"{tag} {current} not yet published, publishing.")
    sys.exit(0)


if __name__ == "__main__":
    main()
