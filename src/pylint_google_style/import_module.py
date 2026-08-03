"""Enforce module-level imports instead of symbol-level imports.

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
    """Check whether a module can be resolved.

    Attempts resolution first via astroid's module manager, then falls back
    to ``importlib.util.find_spec``.

    Args:
        modname: Fully qualified module name, e.g. ``"os.path"``.

    Returns:
        True if the module can be found by either mechanism, False otherwise.
    """
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
    """Determine whether *name* is a submodule of *modname*.

    Args:
        modname: The parent module's fully qualified name (e.g. ``"os"``).
        name: The name imported from *modname* (e.g. ``"path"``).

    Returns:
        True if ``modname.name`` resolves as a module, False if the parent
        is resolvable but the child is not, or None if the parent itself
        cannot be resolved.
    """
    fullname = f"{modname}.{name}"
    if _can_resolve(fullname):
        return True
    if not _can_resolve(modname):
        return None
    return False


def _get_dunder_all(modname: str) -> frozenset[str] | None:
    """Retrieve the ``__all__`` names exported by a module.

    Parses the module's AST via astroid and extracts statically-defined
    ``__all__`` assignments.  Only literal lists/tuples of strings are
    supported; dynamic ``__all__`` construction returns None.

    Args:
        modname: Fully qualified module name.

    Returns:
        A frozenset of exported names, or None if ``__all__`` is not
        defined, not statically analyzable, or the module cannot be
        resolved.
    """
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
    """Find the shallowest ancestor package that re-exports *symbol*.

    Walks up the package hierarchy from the deepest ancestor to the
    shallowest, checking each package's ``__all__`` for *symbol*.  This
    allows the checker to suggest the most concise import path.

    Args:
        module_parts: Components of the fully qualified module name,
            e.g. ``["a", "b", "c"]`` for ``a.b.c``.
        symbol: The symbol name to look for in ancestor ``__all__`` lists.

    Returns:
        A ``(parent_module, last_module)`` tuple for the shallowest
        ancestor that re-exports *symbol*, or None if no ancestor does.
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
            "Import module '%s' instead of symbol '%s'"
            " (use: from %s import %s)",
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
                "help": (
                    "Additional module paths to exclude"
                    " from import-module check."
                ),
            },
        ),
    )

    def __init__(self, linter: lint.PyLinter) -> None:
        """Initialize the checker.

        Args:
            linter: The pylint linter instance.
        """
        super().__init__(linter)
        self._module_exceptions: frozenset[str] = frozenset()

    def open(self) -> None:
        """Prepare the checker before visiting the module.

        Merges the built-in exempt modules with any user-configured
        exceptions from the ``import-module-exceptions`` option.
        """
        self._module_exceptions = EXEMPT_MODULES | frozenset(
            self.linter.config.import_module_exceptions
        )

    def _check_imported_name(
        self,
        node: nodes.ImportFrom,
        name: str,
        module_parts: list[str],
    ) -> None:
        """Check a single imported name and emit messages if needed.

        Skips wildcard imports and dunder names, then verifies whether the
        imported name is a module.  If it is a symbol import, emits either
        ``import-symbol-not-module`` or ``import-symbol-not-package``.

        Args:
            node: The ``from ... import ...`` AST node.
            name: The specific name being imported.
            module_parts: Components of the source module's dotted path.
        """
        # Skip wildcard imports (handled by other checkers).
        if name == "*":
            return

        # Skip __all__, __version__, etc.
        if name.startswith("__") and name.endswith("__"):
            return

        # Use import resolution to check if the name is a module.
        result = _is_module(node.modname, name)
        if result is None:
            self.add_message(
                "import-module-unresolvable",
                node=node,
                args=(node.modname, name, node.modname),
            )
            return

        if result:
            return

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

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Visit a ``from ... import ...`` statement.

        Skips ``__init__.py`` files, relative imports, and modules listed
        in the exception set, then delegates per-name checking to
        :meth:`_check_imported_name`.

        Args:
            node: The import-from AST node being visited.
        """
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
            self._check_imported_name(node, name, module_parts)


def register(linter: lint.PyLinter) -> None:
    """Register the checker with pylint.

    Registration is idempotent: under the parallel runner (``pylint -j 2``)
    pylint re-imports plugins in each worker via
    ``load_plugin_modules(..., force=True)`` on top of the already-registered
    checker carried over in the pickled linter.  Without this guard the
    checker would be registered twice per worker and emit every message
    twice.

    Args:
        linter: The pylint linter instance.
    """
    for checker in linter.get_checkers():
        if isinstance(checker, ImportModuleChecker):
            return
    linter.register_checker(ImportModuleChecker(linter))
