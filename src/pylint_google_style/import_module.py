"""Pylint plugin to enforce module-level imports instead of symbol-level imports.

This plugin detects patterns like:
    from a.b.c.hello import HelloClass
    from b.c.d.func import hello_func

And suggests instead:
    from a.b.c import hello
    from b.c.d import func

    hello.HelloClass
    func.hello_func

The rationale is that module-level imports:
1. Make it clearer where symbols come from when reading code
2. Avoid namespace pollution
3. Make mocking easier in tests

See: https://google.github.io/styleguide/pyguide.html#22-imports
"""

import importlib.util

import astroid
from astroid import exceptions as astroid_exceptions
from astroid import nodes
from pylint import checkers, lint

# Modules exempt from the import check per Google Python Style Guide.
# Only typing-related modules are exempt (for static analysis support).
EXEMPT_MODULES = frozenset(
    {
        "__future__",
        "typing",
        "typing_extensions",
        "collections.abc",
    }
)


def _can_resolve(modname: str) -> bool:
    """Return True if *modname* can be resolved by astroid or importlib."""
    try:
        astroid.MANAGER.ast_from_module_name(modname)
        return True
    except astroid_exceptions.AstroidImportError:
        pass
    try:
        return importlib.util.find_spec(modname) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _is_module(modname: str, name: str) -> bool | None:
    """Check if 'name' is a submodule of 'modname'.

    Returns True if resolvable as a module, False if the parent is
    resolvable but the child is not, None if the parent itself is
    unresolvable.
    """
    fullname = f"{modname}.{name}"
    if _can_resolve(fullname):
        return True
    if not _can_resolve(modname):
        return None
    return False


def _get_dunder_all(modname: str) -> frozenset[str] | None:
    """Return the set of names in *modname*'s ``__all__``, or None."""
    try:
        module = astroid.MANAGER.ast_from_module_name(modname)
    except astroid_exceptions.AstroidImportError:
        return None

    all_nodes = module.locals.get("__all__")
    if not all_nodes:
        return None

    assign_name = all_nodes[0]
    parent = assign_name.parent
    if not isinstance(parent, (nodes.Assign, nodes.AnnAssign)):
        return None

    value = parent.value
    if not isinstance(value, (nodes.List, nodes.Tuple)):
        return None

    names: list[str] = []
    for elt in value.elts:
        if isinstance(elt, nodes.Const) and isinstance(elt.value, str):
            names.append(elt.value)
        else:
            return None

    return frozenset(names)


def _find_reexport_ancestor(
    module_parts: list[str], symbol: str
) -> tuple[str, str] | None:
    """Walk up ancestor packages looking for *symbol* in ``__all__``.

    Returns ``(parent_module, last_module)`` for the shallowest ancestor that
    re-exports *symbol*, or ``None``.
    """
    for i in range(2, len(module_parts)):
        ancestor = ".".join(module_parts[:i])
        all_names = _get_dunder_all(ancestor)
        if all_names is not None and symbol in all_names:
            return ".".join(module_parts[: i - 1]), module_parts[i - 1]
    return None


class ImportModuleChecker(checkers.BaseChecker):
    """Checker for enforcing module-level imports."""

    name = "import-module"
    msgs = {
        "C9001": (
            "Import module '%s' instead of symbol '%s' (use: from %s import %s)",
            "import-symbol-not-module",
            "Prefer importing modules over symbols for better code clarity. "
            "Instead of 'from a.b.c import Symbol', use 'from a.b import c' "
            "and access as 'c.Symbol'.",
        ),
        "C9003": (
            "Import module '%s' instead of symbol '%s' (use: import %s)",
            "import-symbol-not-package",
            "Prefer importing the top-level package over symbols. "
            "Instead of 'from pkg import Symbol', use 'import pkg' "
            "and access as 'pkg.Symbol'.",
        ),
        "W9001": (
            "Cannot verify import '%s.%s': parent module '%s' is not installed",
            "import-module-unresolvable",
            "The parent module could not be resolved (likely not installed). "
            "The import was not checked.",
        ),
    }
    options = (
        (
            "import-module-exceptions",
            {
                "default": (),
                "type": "csv",
                "metavar": "<modules>",
                "help": "Additional module paths to exclude from import-module check.",
            },
        ),
    )

    def __init__(self, linter: lint.PyLinter) -> None:
        super().__init__(linter)
        self._module_exceptions: frozenset[str] = frozenset()

    def open(self) -> None:
        """Called before visiting the module."""
        self._module_exceptions = EXEMPT_MODULES | frozenset(
            self.linter.config.import_module_exceptions
        )

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Check import-from statements."""
        # Skip __init__.py files (re-exporting symbols is valid there).
        module = node.root()
        if module.file and module.file.endswith("__init__.py"):
            return

        # Skip relative imports (handled by relative_import checker).
        if node.level is not None and node.level > 0:
            return

        if node.modname is None:
            return

        # Check if the base module is in exceptions (typing-related modules).
        module_parts = node.modname.split(".")
        for i in range(len(module_parts)):
            prefix = ".".join(module_parts[: i + 1])
            if prefix in self._module_exceptions:
                return

        # Check each imported name.
        for name, _ in node.names:
            # Skip wildcard imports (handled by other checkers).
            if name == "*":
                continue

            # Skip __all__, __version__, etc.
            if name.startswith("__") and name.endswith("__"):
                continue

            # Use import resolution to check if the name is a module.
            result = _is_module(node.modname, name)
            if result is None:
                self.add_message(
                    "import-module-unresolvable",
                    node=node,
                    args=(node.modname, name, node.modname),
                )
                continue

            if result:
                continue

            # The name is not a module, so it's a symbol import.  Flag it.
            if len(module_parts) == 1:
                self.add_message(
                    "import-symbol-not-package",
                    node=node,
                    args=(node.modname, name, node.modname),
                )
            else:
                parent_module = ".".join(module_parts[:-1])
                last_module = module_parts[-1]
                reexport = _find_reexport_ancestor(module_parts, name)
                if reexport is not None:
                    parent_module, last_module = reexport
                self.add_message(
                    "import-symbol-not-module",
                    node=node,
                    args=(node.modname, name, parent_module, last_module),
                )


def register(linter: lint.PyLinter) -> None:
    """Register the checker with pylint."""
    linter.register_checker(ImportModuleChecker(linter))
