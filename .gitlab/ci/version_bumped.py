"""Check if the current version has a minor/major bump over the latest tag.

Exit 0 if a bump is detected (should publish), exit 1 otherwise.
"""

import subprocess
import sys
import tomllib
import pathlib


def get_current_version() -> str:
    """Read the version from pyproject.toml.

    Returns:
        The version string, e.g. ``"0.2.0"``.
    """
    data = tomllib.loads(
        pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    )
    return data["project"]["version"]


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
    """Compare current version against the latest git tag."""
    current = get_current_version()
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
