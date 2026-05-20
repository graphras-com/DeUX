# Contributing to DeUX

Thank you for your interest in contributing to DeUX! This guide covers everything
you need to get started.

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **System libraries:**
  - macOS: `brew install hidapi`
  - Linux (Debian/Ubuntu): `sudo apt install libhidapi-dev`

## Setup

```bash
git clone git@github.com:graphras-com/DeUX.git
cd DeUX
uv sync --extra test
```

This installs all runtime and test dependencies using the pinned `uv.lock`.

## Development Workflow

Every contribution **must** follow this sequence:

1. **Branch from an up-to-date `main`:**

   ```bash
   git checkout main && git pull
   git checkout -b <prefix>/<descriptive-name>
   ```

   Use a prefix that matches the type of change: `feat/`, `fix/`, `docs/`,
   `refactor/`, `test/`, `chore/`.

2. **Make your changes.**

3. **Run the full quality gate** — all checks must pass before committing:

   ```bash
   ruff check .                    # lint
   mypy                            # type-check (strict mode)
   pytest tests/ --cov=deux --cov-report=term-missing --cov-fail-under=95
   ```

4. **Commit** with a clear, descriptive message.

5. **Push and open a pull request:**

   ```bash
   git push -u origin <branch>
   gh pr create --title "..." --body "..."
   ```

> **Never commit directly to `main`.** No exceptions.

## Code Style

- **Formatter/Linter:** [Ruff](https://docs.astral.sh/ruff/) — line length 100,
  target Python 3.11.
- **Type checking:** mypy in strict mode. Add type annotations to all public APIs.
- **Docstrings:** NumPy-style for all public modules, classes, methods, and functions.
  See the example below.

```python
def connect(device_id: str, timeout: float = 5.0) -> bool:
    """Open a connection to a Stream Deck device.

    Parameters
    ----------
    device_id : str
        Serial number or path of the target device.
    timeout : float, default=5.0
        Seconds to wait before aborting the connection attempt.

    Returns
    -------
    bool
        True if the connection was established successfully.

    Raises
    ------
    ConnectionError
        If the device cannot be reached within the timeout.
    """
```

## Testing

- All tests live under `tests/`.
- Hardware is fully mocked via `conftest.py` fixtures — no real Stream Deck needed.
- Async tests run automatically (`asyncio_mode = "auto"`); no decorator required.
- **Coverage threshold: 95%.** New code must include tests that maintain or raise
  this bar.

Run a single file or test:

```bash
pytest tests/test_screen.py          # single file
pytest -k test_name                  # single test by name
```

## Project Layout

```
src/deux/
├── dui/        # .dui package format (SVG layout, YAML manifest, data bindings)
├── render/     # Image rendering and metrics
├── runtime/    # Device discovery, capabilities, transport
├── tools/      # CLI utilities
└── ui/         # Screen, KeySlot, EncoderSlot, TouchStrip controls
```

## CI Pipeline

Every pull request runs the following checks on Python 3.11, 3.12, and 3.13:

| Check | Command |
|-------|---------|
| Lint | `ruff check .` |
| Build | Hatchling package build |
| Type-check | `mypy` |
| Tests + coverage | `pytest --cov=deux --cov-fail-under=95` |
| Secret scanning | gitleaks |

All checks must pass for a PR to be merged.

## Immutable Collection Convention

Public properties that expose internal collections **must not** leak mutable
references. Follow these rules:

| Internal type | Return strategy | Return type annotation |
|---------------|----------------|------------------------|
| `dict` | `MappingProxyType(self._x)` | `Mapping[K, V]` |
| `list` | `list(self._x)` (shallow copy) | `list[T]` |
| `set` | `frozenset(self._x)` | `frozenset[T]` |

- Import `Mapping` from `collections.abc` and `MappingProxyType` from `types`.
- If the internal value can be `None`, return `None` directly (no copy needed).
- Mutation must go through dedicated setter methods (e.g., `set_card()`).

## Reporting Issues

Open an issue on GitHub with:

- A clear title and description of the problem or suggestion.
- Steps to reproduce (for bugs).
- Expected vs. actual behavior.
- Python version and OS.

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE).
