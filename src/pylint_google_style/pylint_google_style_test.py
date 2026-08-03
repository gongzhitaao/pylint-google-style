"""Tests that exercise the plugins as a whole through the pylint runner.

Unlike the per-checker ``*_test.py`` modules, these tests load every plugin
in this package together and drive pylint end to end, guarding behaviour that
only shows up at the runner level (e.g. the parallel runner).

Where a test needs the parallel runner it invokes pylint as a subprocess and
parses its output: the parallel runner requires a picklable reporter, so
``CollectingReporter`` cannot be used in-process.
"""

from __future__ import annotations

import collections
import pathlib
import subprocess
import sys

_PLUGINS = (
    "pylint_google_style.import_module,pylint_google_style.relative_import"
)
_MESSAGES = "import-symbol-not-module,relative-import"


def _make_package(root: pathlib.Path) -> None:
    """Create a package whose modules each trigger both checkers."""
    pkg = root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "sibling.py").write_text("thing = 1\n")
    for i in range(1, 5):
        (pkg / f"mod{i}.py").write_text(
            "from os.path import join\nfrom .sibling import thing\n"
        )


def _run_pylint(package: pathlib.Path, jobs: int) -> list[str]:
    """Run pylint on *package* and return the message lines it prints."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pylint",
            f"--load-plugins={_PLUGINS}",
            "--disable=all",
            f"--enable={_MESSAGES}",
            "--jobs",
            str(jobs),
            "pkg",
        ],
        cwd=package,
        capture_output=True,
        text=True,
        check=False,
    )
    return [
        line
        for line in result.stdout.splitlines()
        if "C9001" in line or "C9002" in line
    ]


class ParallelRunnerTest:
    """Test cases guarding against duplicate messages under ``-j``."""

    def test_no_duplicate_messages_with_parallel_jobs(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Each message should be emitted once under ``-j 2``, as with ``-j 1``."""
        _make_package(tmp_path)

        serial = _run_pylint(tmp_path, jobs=1)
        parallel = _run_pylint(tmp_path, jobs=2)

        # No line is emitted more than once under the parallel runner.
        duplicates = [
            line
            for line, count in collections.Counter(parallel).items()
            if count > 1
        ]
        assert not duplicates

        # The parallel runner reports exactly the same messages as the serial
        # runner.
        assert sorted(parallel) == sorted(serial)
