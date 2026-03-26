"""Decide whether to publish the package.

Publish (exit 0) when:
- No package exists on the GitLab Package Registry yet, OR
- The minor or major version has been bumped compared to the latest git tag.

Skip (exit 1) otherwise.
"""

import os
import subprocess
import sys
import tomllib
import pathlib
import urllib.request
import json


def get_current_version() -> str:
    """Read the version from pyproject.toml.

    Returns:
        The version string, e.g. ``"0.2.0"``.
    """
    data = tomllib.loads(
        pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    )
    return data["project"]["version"]


def get_package_name() -> str:
    """Read the package name from pyproject.toml.

    Returns:
        The package name, e.g. ``"pylint-google-style"``.
    """
    data = tomllib.loads(
        pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    )
    return data["project"]["name"]


def package_exists_on_registry() -> bool:
    """Check whether any version of this package exists on the GitLab registry.

    Returns:
        True if at least one package version is published.
    """
    api_url = os.environ["CI_API_V4_URL"]
    project_id = os.environ["CI_PROJECT_ID"]
    token = os.environ["CI_JOB_TOKEN"]
    name = get_package_name()

    url = (
        f"{api_url}/projects/{project_id}"
        f"/packages?package_type=pypi&package_name={name}"
    )
    req = urllib.request.Request(url, headers={"JOB-TOKEN": token})
    with urllib.request.urlopen(req) as resp:
        packages = json.loads(resp.read())
    return len(packages) > 0


def get_latest_tag_version() -> str | None:
    """Get the version from the most recent git tag.

    Returns:
        The tag name (stripped of leading ``v`` if present), or None if
        no tags exist.
    """
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip().lstrip("v")


def minor_version(version: str) -> str:
    """Extract the major.minor portion of a version string.

    Args:
        version: A version string, e.g. ``"1.2.3"``.

    Returns:
        The ``"major.minor"`` prefix, e.g. ``"1.2"``.
    """
    parts = version.split(".")
    return f"{parts[0]}.{parts[1]}"


def main() -> None:
    """Decide whether to publish."""
    current = get_current_version()

    if not package_exists_on_registry():
        print(f"No package on registry yet.  Publishing {current}.")
        sys.exit(0)

    previous = get_latest_tag_version()

    if previous is None:
        print(f"No previous tag found.  Current version: {current}")
        sys.exit(0)

    curr_minor = minor_version(current)
    prev_minor = minor_version(previous)

    if curr_minor != prev_minor:
        print(f"Version bump detected: {previous} -> {current}")
        sys.exit(0)
    else:
        print(
            f"No minor/major version bump ({previous} -> {current}), skipping."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
