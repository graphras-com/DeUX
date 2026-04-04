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

Deckboard is an asyncio-native Python 3.11+ library for Elgato Stream Deck+ devices. It wraps the low-level `python-elgato-streamdeck` HID library and provides a high-level API for key slots, encoder slots, touchscreen cards, icons, and screen management.

### Repository structure

The codebase is organized into four top-level packages plus an integrations package:

```
src/deckboard/              # Library source
  __init__.py               # Public API surface — re-exports from runtime, render, ui, presets

  runtime/                  # Device lifecycle, events, transport
    __init__.py             # Re-exports: Deck, DeckError, DeviceInfo, event types, Transport
    deck.py                 # Main Deck class — entry point, event loop, rendering
    device_info.py          # DeviceInfo dataclass
    events.py               # Event dataclasses (KeyEvent, DialTurnEvent, etc.), EventType enum, type aliases
    transport.py            # Async bridge for HID callbacks (sync thread → asyncio queue)

  render/                   # Image rendering, fonts, icons
    __init__.py             # Re-exports: IconManager, IconError, render helpers
    debug_grid.py           # Debug grid overlay for development
    fonts.py                # Font loading and management
    icons.py                # IconManager — Iconify API fetching, SVG→PNG, disk/memory cache
    key_renderer.py         # Key image rendering helpers, layout constants, JPEG encoding
    metrics.py              # Render metrics and constants
    touch_renderer.py       # Touchscreen rendering helpers

  ui/                       # UI primitives and concrete components
    __init__.py             # Re-exports all UI types from subpackages
    screen.py               # Screen class — named layout of key slots, encoder slots, cards
    touch_strip.py          # TouchStrip — container for cards on the touchscreen

    cards/                  # Card types (touchscreen panels)
      __init__.py           # Re-exports: Card, StackCard, StatusCard
      base.py               # Card ABC — abstract base for touchscreen cards
      stack.py              # StackCard — generic container for mixed elements
      status.py             # StatusCard — icon + label + value display

    controls/               # Interactive controls bound to physical inputs
      __init__.py           # Re-exports all control types
      base.py               # Control ABC — abstract base for controls
      key_slot.py           # KeySlot class (+ Button alias) — wraps a physical key (0-7)
      encoder_slot.py       # EncoderSlot class (+ Dial alias) — wraps a rotary encoder (0-3)
      range_control.py      # RangeControl/Slider/LargeSlider/SmallSlider hierarchy
      volume.py             # VolumeSlider
      brightness.py         # BrightnessSlider
      temperature.py        # TemperatureSlider
      kelvin.py             # KelvinSlider
      balance.py            # BalanceSlider
      equalizer.py          # EqualizerSlider

    elements/               # Passive display elements within cards
      __init__.py           # Lazy re-exports: LargeText, SmallText, LargeDualValue, SmallDualValue
      base.py               # Element ABC — abstract base for display elements
      text.py               # LargeText, SmallText
      metrics.py            # LargeDualValue, SmallDualValue

  presets/                  # Domain-grouped composite cards
    __init__.py             # Re-exports: EqualizerCard, LightCard, MediaCard
    audio.py                # EqualizerCard — multi-band equalizer card
    lighting.py             # LightCard — light control card
    media.py                # MediaCard — media playback card
    climate.py              # Climate-related presets (future)
    sensors.py              # Sensor-related presets (future)

  integrations/             # External service bindings (not part of core refactor)

tests/                      # One test file per source module
  conftest.py               # Shared fixtures (mock device, sample images, etc.)
```

### Class naming

The canonical class names reflect their hardware role:

| Canonical name   | Backward-compatible alias | Module                          |
|------------------|---------------------------|---------------------------------|
| `KeySlot`        | `Button`                  | `ui.controls.key_slot`          |
| `EncoderSlot`    | `Dial`                    | `ui.controls.encoder_slot`      |
| `RangeControl`   | `Slider`                  | `ui.controls.range_control`     |
| `Screen`         | —                         | `ui.screen` (was `Page`)        |
| `Card`           | —                         | `ui.cards.base` (was `Widget`)  |
| `TouchStrip`     | —                         | `ui.touch_strip` (was `TouchScreen`) |

Both canonical names and aliases are exported from `deckboard.__init__`.

## Build / lint / test commands

```bash
# Install in editable mode with test deps
pip install -e ".[test]"

# Full test suite with coverage (CI gate = 95%)
python -m pytest tests/ --cov=deckboard --cov-report=term-missing --cov-fail-under=95

# Single test file
python -m pytest tests/test_deck.py -v

# Single test class
python -m pytest tests/test_key_slot.py::TestKeySlotSetIcon -v

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
"""KeySlot class: wraps a physical key on the Stream Deck."""

from __future__ import annotations

import logging                          # stdlib
from typing import TYPE_CHECKING

from PIL import Image                   # third-party

from deckboard.runtime.events import AsyncHandler  # local
```

Use `TYPE_CHECKING` blocks for imports only needed by type checkers (Ruff `TCH` rule):
```python
if TYPE_CHECKING:
    from StreamDeck.Devices.StreamDeck import StreamDeck
```

### Type annotations

- **mypy strict mode** — annotate every function signature, every variable where inference is ambiguous.
- Use modern union syntax: `str | None`, `int | float`, `tuple[int, int]`.
- Use `@dataclass(frozen=True, slots=True)` for immutable data (see `runtime/events.py`).
- Type aliases go in `runtime/events.py`: `AsyncHandler = Callable[..., Coroutine[Any, Any, None]]`.

### Naming conventions

- Classes: `PascalCase` — `Deck`, `KeySlot`, `RangeControl`, `VolumeSlider`
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
- **Dirty tracking** — `is_dirty` / `mark_clean()` / `mark_dirty()` on cards and key slots.
- **Abstract base classes** — `Card(ABC)` with `@abstractmethod render()`.
- **Thread-safe bridge** — `runtime/transport.py` uses `loop.call_soon_threadsafe()` to enqueue events from the HID reader thread.

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

- One file per source module: `test_key_slot.py`, `test_deck.py`, `test_widgets_volume.py`.
- Group related tests in classes: `class TestKeySlotSetIcon:`, `class TestDeckDispatch:`.
- Shared fixtures in `conftest.py` (key slots, encoder slots, cards, mock device, sample images).
- Test edge cases and error paths, not just the happy path.

### Example test structure

```python
"""Tests for deckboard.ui.controls.key_slot — KeySlot class."""

from __future__ import annotations
import pytest
from deckboard.ui.controls.key_slot import KeySlot

class TestKeySlotSetIcon:
    def test_sets_icon_name(self, key_slot: KeySlot):
        key_slot.set_icon("mdi:home")
        assert key_slot.icon_name == "mdi:home"

    def test_marks_dirty(self, key_slot: KeySlot):
        key_slot.mark_clean()
        key_slot.set_icon("mdi:home")
        assert key_slot.is_dirty is True
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
