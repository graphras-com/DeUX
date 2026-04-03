# AGENTS.md

Instructions for AI coding agents working on the **deckboard** repository.

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
   python -m pytest tests/ --cov=deckboard --cov-report=term-missing --cov-fail-under=95
   ```
4. **Commit** — only after all tests pass.
5. **Push and create a PR**:
   ```
   git push -u origin <branch>
   gh pr create --title "..." --body "..."
   ```

**Never commit directly to `main`.** No exceptions.

## Project overview

Deckboard is an asyncio-native Python 3.11+ library for Elgato Stream Deck+ devices. It wraps the low-level `python-elgato-streamdeck` HID library and provides a high-level API for buttons, dials, touchscreen widgets, icons, and page management.

### Repository structure

```
src/deckboard/              # Library source
  __init__.py               # Public API surface and __all__
  _transport.py             # Async bridge for HID callbacks (sync thread → asyncio queue)
  button.py                 # Button abstraction (keys 0-7)
  deck.py                   # Main Deck class — entry point, event loop, rendering
  dial.py                   # Dial abstraction (rotary encoders 0-3)
  icon.py                   # Icon fetching (Iconify API), SVG→PNG, disk/memory cache
  image.py                  # Image rendering helpers, layout constants, JPEG encoding
  page.py                   # Page management (named layouts of buttons/dials/widgets)
  touchscreen.py            # Abstract Widget base class, TouchScreen container
  types.py                  # Event dataclasses, enums, type aliases
  widgets/                  # Concrete widget implementations
    __init__.py             # Re-exports all widget classes
    slider.py               # Abstract Slider/LargeSlider/SmallSlider base classes
    slider_widget.py        # SliderWidget — groups multiple sliders under one dial
    icon_widget.py          # IconWidget — icon + label + value display
    text.py                 # LargeText, SmallText elements
    touch_panel.py          # TouchPanel — generic container for mixed elements
    volume.py, brightness.py, temperature.py, kelvin.py, balance.py, equalizer.py
tests/                      # One test file per source module
  conftest.py               # Shared fixtures (mock device, sample images, etc.)
```

## Build / lint / test commands

```bash
# Install in editable mode with test deps
pip install -e ".[test]"

# Full test suite with coverage (CI gate = 95%)
python -m pytest tests/ --cov=deckboard --cov-report=term-missing --cov-fail-under=95

# Single test file
python -m pytest tests/test_deck.py -v

# Single test class
python -m pytest tests/test_button.py::TestButtonSetIcon -v

# Single test method
python -m pytest tests/test_deck.py::TestDeckEventLoop::test_event_loop_timeout_continues -v

# Lint (Ruff)
ruff check src/ tests/

# Type check (mypy strict)
mypy src/deckboard/
```

## Code style

### Imports and file header

Every `.py` file must start with:
1. A module docstring (one-line summary of the module's purpose)
2. `from __future__ import annotations`
3. Stdlib imports, then third-party, then local — Ruff's `I` rule enforces isort ordering

```python
"""Button class: wraps a physical key on the Stream Deck."""

from __future__ import annotations

import logging                          # stdlib
from typing import TYPE_CHECKING

from PIL import Image                   # third-party

from .types import AsyncHandler         # local (relative)
```

Use `TYPE_CHECKING` blocks for imports only needed by type checkers (Ruff `TCH` rule):
```python
if TYPE_CHECKING:
    from StreamDeck.Devices.StreamDeck import StreamDeck
```

### Type annotations

- **mypy strict mode** — annotate every function signature, every variable where inference is ambiguous.
- Use modern union syntax: `str | None`, `int | float`, `tuple[int, int]`.
- Use `@dataclass(frozen=True, slots=True)` for immutable data (see `types.py`).
- Type aliases go in `types.py`: `AsyncHandler = Callable[..., Coroutine[Any, Any, None]]`.

### Naming conventions

- Classes: `PascalCase` — `Deck`, `Button`, `SliderWidget`, `VolumeSlider`
- Functions/methods: `snake_case` — `set_value()`, `render_key_image()`
- Private attributes: leading underscore — `self._device`, `self._running`
- Module-level constants: `UPPER_SNAKE_CASE` — `WIDGET_WIDTH`, `KEY_SIZE`
- Private module constants: leading underscore — `_KEY_COUNT = 8`, `_ICONIFY_API`
- Loggers: one per module — `logger = logging.getLogger(__name__)`

### Error handling

- Define module-specific exception classes inheriting from `Exception`:
  `DeckError`, `IconError`.
- Use `raise ... from e` to chain exceptions.
- Guard state access: raise early with descriptive messages
  (e.g., `raise DeckError("Device not opened")`).
- Log unexpected errors with `logger.exception(...)` and continue or re-raise.
- Validate index arguments with range checks:
  `if not 0 <= index < _KEY_COUNT: raise IndexError(...)`.

### Patterns used throughout

- **Async context manager** for resource lifecycle (`Deck.__aenter__`/`__aexit__`).
- **Decorator-based event registration** — `@button.on_press`, `@dial.on_turn`.
- **Method chaining** — mutators return `self` (e.g., `button.set_icon(...).set_label(...)`).
- **Dirty tracking** — `is_dirty` / `mark_clean()` / `mark_dirty()` on widgets and buttons.
- **Abstract base classes** — `Widget(ABC)` with `@abstractmethod render()`.
- **Thread-safe bridge** — `_transport.py` uses `loop.call_soon_threadsafe()` to enqueue events from the HID reader thread.

### Ruff lint rules (`pyproject.toml`)

```
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]
target-version = "py311"
```

## Testing

### Requirements

- **Coverage >= 95%** — CI enforces this gate.
- **All hardware is mocked** — tests run without a physical Stream Deck.
- `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorator needed.
- Use `unittest.mock.MagicMock` / `AsyncMock` for device mocking.
- Use `respx` for mocking HTTP requests (icon fetching).

### Test file conventions

- One file per source module: `test_button.py`, `test_deck.py`, `test_widgets_volume.py`.
- Group related tests in classes: `class TestButtonSetIcon:`, `class TestDeckDispatch:`.
- Shared fixtures in `conftest.py` (buttons, dials, widgets, mock device, sample images).
- Test edge cases and error paths, not just the happy path.

### Example test structure

```python
"""Tests for deckboard.button — Button class."""

from __future__ import annotations
import pytest
from deckboard.button import Button

class TestButtonSetIcon:
    def test_sets_icon_name(self, button: Button):
        button.set_icon("mdi:home")
        assert button.icon_name == "mdi:home"

    def test_marks_dirty(self, button: Button):
        button.mark_clean()
        button.set_icon("mdi:home")
        assert button.is_dirty is True
```

## Branch naming

- `feature/<name>` — new functionality
- `fix/<name>` — bug fixes
- `refactor/<name>` — code restructuring
- `docs/<name>` — documentation
- `ci/<name>` — CI/CD changes

## Commit messages

Start with an imperative verb: `Add`, `Fix`, `Update`, `Refactor`, `Remove`.
First line: concise summary. Optional body: explain the "why".

## CI/CD

CI runs on pushes to `main`, PRs targeting `main`, and manual dispatch.
Tests run on Python 3.11, 3.12, 3.13 (Ubuntu). System deps: `libcairo2-dev`, `libhidapi-dev`.

## Other reminders

- Do not commit secrets. The `.gitignore` is configured.
- Mock all hardware — no physical device required for tests.
- Add tests for any new code to maintain 95%+ coverage.
