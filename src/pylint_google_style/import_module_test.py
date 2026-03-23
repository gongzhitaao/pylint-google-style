"""Tests for the import_module pylint plugin."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest
from pylint import lint, reporters


def _run_pylint(source_path: str, extra_args: list[str] | None = None) -> list:
    reporter = reporters.CollectingReporter()
    args = [
        "--load-plugins=pylint_google_style.import_module",
        "--disable=all",
        "--enable=import-symbol-not-module,"
        "import-symbol-not-package,"
        "import-module-unresolvable",
        # CollectingReporter is not picklable for parallel workers.
        "--jobs=1",
    ]
    if extra_args:
        args.extend(extra_args)
    args.append(source_path)
    lint.Run(
        args,
        reporter=reporter,
        exit=False,
    )
    return reporter.messages  # type: ignore[no-any-return]


class ImportModuleCheckerTest:
    """Test cases for ImportModuleChecker."""

    def test_flags_function_import_basename(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should flag: from os.path import basename (basename is a function)."""
        f = tmp_path / "example.py"
        f.write_text("from os.path import basename\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-symbol-not-module"

    def test_flags_function_import_dirname(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should flag: from os.path import dirname (dirname is a function)."""
        f = tmp_path / "example.py"
        f.write_text("from os.path import dirname\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-symbol-not-module"

    def test_flags_constant_import(self, tmp_path: pathlib.Path) -> None:
        """Should flag: from os.path import sep (sep is a constant)."""
        f = tmp_path / "example.py"
        f.write_text("from os.path import sep\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-symbol-not-module"

    def test_flags_real_function_import(self, tmp_path: pathlib.Path) -> None:
        """Should flag: from os.path import join (join is a function, not a module)."""
        f = tmp_path / "example.py"
        f.write_text("from os.path import join\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-symbol-not-module"

    def test_allows_module_import(self, tmp_path: pathlib.Path) -> None:
        """Should allow: from os import path (path is a module)."""
        f = tmp_path / "example.py"
        f.write_text("from os import path\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_allows_typing_imports(self, tmp_path: pathlib.Path) -> None:
        """Should allow: from typing import Optional (exempt per Google style)."""
        f = tmp_path / "example.py"
        f.write_text("from typing import Optional\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_allows_typing_extensions_imports(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should allow: from typing_extensions import Self (exempt)."""
        f = tmp_path / "example.py"
        f.write_text("from typing_extensions import Self\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_allows_collections_abc_imports(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should allow: from collections.abc import Mapping (exempt)."""
        f = tmp_path / "example.py"
        f.write_text("from collections.abc import Mapping\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_flags_single_level_unresolvable_import(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should warn: from mypackage import MyClass (unresolvable package)."""
        f = tmp_path / "example.py"
        f.write_text("from mypackage import MyClass\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-module-unresolvable"

    def test_allows_single_level_module_import(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should allow: from os import path (single-level module import)."""
        f = tmp_path / "example.py"
        f.write_text("from os import path\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_allows_future_import(self, tmp_path: pathlib.Path) -> None:
        """Should allow: from __future__ import annotations."""
        f = tmp_path / "example.py"
        f.write_text("from __future__ import annotations\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_flags_single_level_symbol_import(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should flag: from dataclasses import dataclass (single-level symbol)."""
        f = tmp_path / "example.py"
        f.write_text("from dataclasses import dataclass\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-symbol-not-package"

    def test_allows_dunder_imports(self, tmp_path: pathlib.Path) -> None:
        """Should allow: from a.b.c import __version__."""
        f = tmp_path / "example.py"
        f.write_text("from a.b.c import __version__\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_allows_init_file_reexports(self, tmp_path: pathlib.Path) -> None:
        """Should allow symbol imports in __init__.py files."""
        f = tmp_path / "__init__.py"
        f.write_text("from a.b.hello import HelloClass\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_skips_relative_imports(self, tmp_path: pathlib.Path) -> None:
        """Should skip relative imports (handled by relative_import checker)."""
        f = tmp_path / "example.py"
        f.write_text("from .module import SomeClass\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    @pytest.mark.skipif(
        importlib.util.find_spec("hydra") is None, reason="hydra not installed"
    )
    def test_allows_module_import_via_importlib_fallback(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should allow: from hydra.core import config_store (importlib fallback)."""
        f = tmp_path / "example.py"
        f.write_text("from hydra.core import config_store\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 0

    def test_warns_unresolvable_parent(self, tmp_path: pathlib.Path) -> None:
        """Should warn when parent package is not installed (cannot determine)."""
        f = tmp_path / "example.py"
        f.write_text("from notinstalled.pkg import SomeName\n")
        msgs = _run_pylint(str(f))
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-module-unresolvable"

    def test_suggests_reexport_from_ancestor(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should suggest shallower import when ancestor __all__ re-exports."""
        pkg = tmp_path / "testpkg" / "a" / "b"
        pkg.mkdir(parents=True)
        (tmp_path / "testpkg" / "__init__.py").write_text("")
        (tmp_path / "testpkg" / "a" / "__init__.py").write_text(
            '__all__ = ["MyClass"]\n'
        )
        (tmp_path / "testpkg" / "a" / "b" / "__init__.py").write_text("")
        (tmp_path / "testpkg" / "a" / "b" / "mod.py").write_text(
            "class MyClass: pass\n"
        )
        f = tmp_path / "example.py"
        f.write_text("from testpkg.a.b.mod import MyClass\n")
        msgs = _run_pylint(
            str(f),
            extra_args=[
                f"--init-hook=import sys; sys.path.insert(0, {str(tmp_path)!r})"
            ],
        )
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-symbol-not-module"
        assert "from testpkg import a" in msgs[0].msg

    def test_default_suggestion_without_reexport(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Should use default suggestion when no ancestor __all__ re-exports."""
        pkg = tmp_path / "testpkg2" / "a" / "b"
        pkg.mkdir(parents=True)
        (tmp_path / "testpkg2" / "__init__.py").write_text("")
        (tmp_path / "testpkg2" / "a" / "__init__.py").write_text("")
        (tmp_path / "testpkg2" / "a" / "b" / "__init__.py").write_text("")
        (tmp_path / "testpkg2" / "a" / "b" / "mod.py").write_text(
            "class MyClass: pass\n"
        )
        f = tmp_path / "example.py"
        f.write_text("from testpkg2.a.b.mod import MyClass\n")
        msgs = _run_pylint(
            str(f),
            extra_args=[
                f"--init-hook=import sys; sys.path.insert(0, {str(tmp_path)!r})"
            ],
        )
        assert len(msgs) == 1
        assert msgs[0].symbol == "import-symbol-not-module"
        assert "from testpkg2.a.b import mod" in msgs[0].msg
