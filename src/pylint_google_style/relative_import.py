"""Pylint plugin to enforce absolute imports over relative imports.

This plugin detects patterns like:
    from .module import something
    from ..utils import helper

And suggests using absolute imports instead:
    from mypackage.subpackage.module import something
    from mypackage.utils import helper

The rationale is that absolute imports:
1. Prevent unintentional duplicate imports
2. Make the code's dependencies explicit
3. Are easier to understand and refactor

See: https://google.github.io/styleguide/pyguide.html#22-imports
"""

from astroid import nodes
from pylint import checkers, lint


class RelativeImportChecker(checkers.BaseChecker):
    """Checker for flagging relative imports."""

    name = "relative-import"
    msgs = {
        "C9002": (
            "Use absolute import instead of relative import '%s'",
            "relative-import",
            "Avoid relative imports. Even if the module is in the same package, "
            "use the full package name. This prevents unintentional duplicate imports.",
        ),
    }

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Check import-from statements for relative imports."""
        # Skip __init__.py files (relative imports are common there for re-exports).
        module = node.root()
        if module.file and module.file.endswith("__init__.py"):
            return

        # Flag relative imports.
        if node.level is not None and node.level > 0:
            dots = "." * node.level
            rel_import = f"{dots}{node.modname}" if node.modname else dots
            self.add_message("relative-import", node=node, args=(rel_import,))


def register(linter: lint.PyLinter) -> None:
    """Register the checker with pylint."""
    linter.register_checker(RelativeImportChecker(linter))
