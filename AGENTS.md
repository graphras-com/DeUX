# AGENTS.md

## Project

DeUX — asyncio-native Python library for Elgato Stream Deck devices. Single package at `src/deux`, built with Hatchling.

## Core Mission

Build a robust, asyncio-native foundation for Stream Deck development centered on a declarative UI model (DUI) that separates interface definition from runtime logic.
The project’s mission is to standardize how keys, encoders, and touchscreen interfaces are described, shared, and executed—enabling reusable, composable UI packages across devices.

Prioritize reliability (auto-discovery, hot-plugging, multi-deck orchestration), consistency (event-driven APIs with predictable behavior), and portability (device-agnostic DUI packages).
Every design decision should move toward a platform-independent ecosystem where developers can create, distribute, and reuse high-quality DUI components through a centralized repository.

Avoid feature sprawl that ties implementations to specific hardware quirks. Instead, abstract capabilities into clean, declarative primitives that scale across current and future devices.


## Setup

```bash
uv sync --extra test        # uses uv.lock; Python 3.11+ required
```

System deps (CI uses `libcairo2-dev libhidapi-dev`; on macOS: `brew install cairo hidapi`).

## Mandatory workflow — read this FIRST

You MUST follow this sequence for every task. Do not write any code before step 1.

1. **Create a branch** from up-to-date `main`:
   ```
   git checkout main && git pull
   git checkout -b <prefix>/<name>
   ```
2. **Do the work.**
3. **Run the full test suite** — every test must pass before you commit:
   ```
   python -m pytest tests/ --cov=deux --cov-report=term-missing --cov-fail-under=95
   ```
4. **Commit** — only after all tests pass.
5. **Push and create a PR**:
   ```
   git push -u origin <branch>
   gh pr create --title "..." --body "..."
   ```

**Never commit directly to `main`.** No exceptions.

## Docstring convention

All AI agents modifying this repository must write NumPy-style docstrings for all relevant Python code.

Use NumPy-style docstrings for:

- Public modules
- Public classes
- Public methods
- Public functions
- Non-obvious private helpers
- Complex test fixtures or utilities

Docstrings must describe:

- Purpose and behavior
- Parameters
- Return values
- Raised exceptions, where relevant
- Side effects, where relevant
- Examples, when useful

Use this format:

```python
def example_function(name: str, retries: int = 3) -> bool:
    """Validate a named operation.

    Parameters
    ----------
    name : str
        Name of the operation to validate.
    retries : int, default=3
        Number of retry attempts before failing.

    Returns
    -------
    bool
        True if the operation is valid, otherwise False.

    Raises
    ------
    ValueError
        If ``name`` is empty.
    """
```

## Commands

```bash
ruff check .                              # lint
mypy                                      # typecheck (strict mode)
pytest                                    # run all tests
pytest --cov=deux --cov-fail-under=95   # tests with coverage gate
pytest tests/test_screen.py               # single test file
pytest -k test_name                       # single test
```

CI runs: lint, build, typecheck, tests (3.11/3.12/3.13), gitleaks. All must pass for the quality gate.

## Architecture

- `src/deux/runtime/` — device discovery, capabilities, transport
- `src/deux/ui/` — Screen, KeySlot, EncoderSlot, TouchStrip controls
- `src/deux/dui/` — `.dui` package format (SVG layout + YAML manifest, data bindings, event maps)
- `src/deux/render/` — image rendering, metrics
- `src/deux/tools/` — CLI utilities

## Testing

- `asyncio_mode = "auto"` — async tests need no `@pytest.mark.asyncio`
- All hardware is mocked via `conftest.py` fixtures (`mock_streamdeck_device`, etc.) — no real device needed
- `.dui` test packages are built in `tmp_path` by `conftest.py` helpers (`card_dui_path`, `key_dui_path`)
- Coverage threshold: **95%**

## Style

- Ruff: line length 100, target py311, rules: E/W/F/I/B/UP/C4/SIM (B008 ignored)
- `tests/*` ignores B011
- mypy strict with `ignore_missing_imports` for `StreamDeck.*` and `cairosvg`
- Wheel packages from `src/deux` (src layout)
