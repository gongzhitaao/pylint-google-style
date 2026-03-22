"""Tests for the relative_import pylint plugin."""

from __future__ import annotations

import pathlib

from pylint import lint, reporters


def _run_pylint(source_path: str) -> list:
    reporter = reporters.CollectingReporter()
    lint.Run(
        [
            "--load-plugins=pylint_google_style.relative_import",
            "--disable=all",
            "--enable=relative-import",
            # CollectingReporter is not picklable for parallel workers.
            "--jobs=1",
            source_path,
        ],
        reporter=reporter,
        exit=False,
    )
    return reporter.messages  # type: ignore[no-any-return]


class RelativeImportCheckerTest:
    """Test cases for RelativeImportChecker."""

    def test_flags_single_dot_relative_import(self, tmp_path: pathlib.Path) -> None:
        """Should flag: from .module import something."""
        f = tmp_path / "example.py"
        f.write_text("from .module import SomeClass\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "relative-import"

    def test_flags_double_dot_relative_import(self, tmp_path: pathlib.Path) -> None:
        """Should flag: from ..module import something."""
        f = tmp_path / "example.py"
        f.write_text("from ..utils import helper\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "relative-import"

    def test_flags_dot_only_import(self, tmp_path: pathlib.Path) -> None:
        """Should flag: from . import something."""
        f = tmp_path / "example.py"
        f.write_text("from . import sibling\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "relative-import"

    def test_allows_absolute_imports(self, tmp_path: pathlib.Path) -> None:
        """Should allow absolute imports."""
        f = tmp_path / "example.py"
        f.write_text("from mypackage.module import SomeClass\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_allows_init_file_relative_imports(self, tmp_path: pathlib.Path) -> None:
        """Should allow relative imports in __init__.py files."""
        f = tmp_path / "__init__.py"
        f.write_text("from .submodule import something\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0
