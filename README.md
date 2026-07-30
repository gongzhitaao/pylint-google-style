# pylint-google-style

Pylint plugins that enforce two import rules from the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#22-imports):

1. **Import modules, not symbols** — prefer `from a.b import c` and reference
   `c.Symbol`, rather than `from a.b.c import Symbol`.
2. **Use absolute imports, not relative imports** — prefer
   `from mypackage.utils import helper` over `from ..utils import helper`.

## Installation

```bash
uv add --dev pylint-google-style
# or
pip install pylint-google-style
```

## Usage

Enable the checkers by loading the plugins in your `.pylintrc`:

```ini
[MAIN]
load-plugins =
    pylint_google_style.import_module,
    pylint_google_style.relative_import
```

Or on the command line:

```bash
pylint --load-plugins=pylint_google_style.import_module,pylint_google_style.relative_import your_package/
```

## Checks

| Code    | Symbol                       | Description                                                              |
| ------- | ---------------------------- | ----------------------------------------------------------------------- |
| `C9001` | `import-symbol-not-module`   | A symbol was imported from a module; import the module instead.         |
| `C9003` | `import-symbol-not-package`  | A symbol was imported from a top-level package; import the package.     |
| `C9002` | `relative-import`            | A relative import was used; use an absolute import instead.             |
| `W9001` | `import-module-unresolvable` | The parent module could not be resolved, so the import was not checked. |

`__init__.py` files are exempt from both checkers, since re-exporting symbols
there is idiomatic.

### Example

```python
# flagged (C9001): symbol imported from a module
from os.path import join

# preferred
from os import path
path.join(...)
```

```python
# flagged (C9002): relative import
from ..utils import helper

# preferred
from mypackage.utils import helper
```

## Configuration

The `import-module` checker accepts additional modules to exempt from the
symbol-vs-module rule (on top of the built-in exemptions for typing-related
modules such as `typing`, `typing_extensions`, `collections.abc`, and
`__future__`):

```ini
[IMPORT-MODULE]
import-module-exceptions =
    numpy,
    pandas
```

## Development

```bash
uv sync
uv run pytest                       # run tests
uv run ruff check .                 # lint
uv run ruff format --check .        # formatting
```

## License

[MIT](LICENSE) © Zhitao Gong
