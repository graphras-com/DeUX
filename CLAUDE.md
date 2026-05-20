# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
uv sync --extra test     # primary install — uses pinned uv.lock; Python 3.11+
```

System libraries (required for HID + SVG rasterisation):
- macOS: `brew install hidapi`
- Linux (Debian/Ubuntu): `sudo apt install libhidapi-dev`

## Quality gate (must pass before commit)

```bash
ruff check .                                                    # lint
mypy                                                            # strict typecheck
pytest tests/ --cov=deux --cov-report=term-missing --cov-fail-under=95
```

CI runs the same three checks across Python 3.11/3.12/3.13 plus a Hatchling build and Gitleaks scan. **Coverage threshold is 95% — new code must keep or raise it.**

Single test / file:
```bash
pytest tests/test_screen.py
pytest -k test_name
```

Run the example against a real device:
```bash
python examples/streamdeck.py
```

## Workflow rules

- **Never commit directly to `main`.** Branch with prefix matching the change type: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`. Push and open a PR via `gh pr create`.
- **NumPy-style docstrings** are mandatory on all public modules, classes, methods, functions (and non-obvious private helpers / complex test fixtures). Sections: Parameters, Returns, Raises (when relevant), Side effects (when relevant). The mkdocstrings docs build relies on this format — see `mkdocs.yml`.
- Ruff config: line length 100, target py311, rules E/W/F/I/B/UP/C4/SIM with B008 ignored. `tests/*` ignores B011.
- mypy is strict; `StreamDeck.*` is the only allowed `ignore_missing_imports` override.

## Architecture

Single package `src/deux` (src layout, Hatchling build). Five subpackages with strict layering:

- **`runtime/`** — device session: `DeckManager` is the **only public entry point**. It owns discovery (`discovery.py`), hot-plug polling, auto-reconnect, and creates `Deck` instances. `Deck` wraps one device, holds `DeviceCapabilities` (auto-detected from hardware), and uses `AsyncTransport` to bridge the synchronous `StreamDeck` library callbacks onto the asyncio loop. Events flow as typed `DeckEvent` subclasses (`KeyEvent`, `EncoderPressEvent`, `EncoderTurnEvent`, `TouchEvent`).
- **`ui/`** — declarative layout primitives attached to a `Deck`: `Screen` is a named layout containing `KeySlot`s, `EncoderSlot`s, an optional `TouchStrip` of `Card`s, and an optional `InfoScreen`. Screens swap atomically via `deck.set_screen(name)`. Slots expose decorator-based handlers (`@key.on_press`, `@encoder.on_turn`, etc.). Available slots/zones are gated by `DeviceCapabilities` — accessing absent hardware raises `DeckError`.
- **`dui/`** — the `.dui` package format: a directory containing `layout.svg` + `manifest.yaml`. `loader.load_package()` parses + validates into a `PackageSpec` (`schema.py`); `DuiCard` / `DuiKey` (`card.py`, `key.py`) wrap a spec to render via `SvgRenderer` and dispatch declared events through `EventMap`. Bindings are typed (text, image, visibility, color, range, slider, toggle, iconify) and drive SVG node attributes at render time. `animator.py` + `spinner.py` handle async spinner refresh; `iconify.py` fetches Iconify icons.
- **`render/`** — pure-image layer: `key_renderer`, `screen_renderer`, `touch_renderer`, `svg_rasterize`, `image_fetch` (caching HTTP loader), and `metrics.py` which derives panel/touch-strip geometry from capabilities.
- **`tools/`** — CLIs invoked as `python -m deux.tools.preview` and `python -m deux.tools.verify` (preview SVGs on a connected deck with optional `--watch`; verify a `.dui` package or a directory of packages with optional `--strict` / `--index`).

Public surface is whatever `deux/__init__.py` re-exports — keep `__all__` accurate when you add or rename symbols.

### Key architectural rules

- **`DeckManager` is the sole device entry point.** Do not instantiate `Deck` directly; receive it via `@manager.on_connect()`.
- **Hardware-agnostic by design.** New behaviour must abstract through `DeviceCapabilities` rather than branching on deck model. Stream Deck+, Mini, Neo, and XL are all supported and tested.
- **Event-driven UI updates** (see `examples/streamdeck.py`): controllers call service methods, services emit async events when state actually changes, controllers subscribe to those events and update bindings. UI reflects *confirmed* state, not *requested* state.
- **`.dui` portability is load-bearing.** Resist tying `.dui` features to specific hardware quirks — the format is meant to be a portable, reusable UI artifact across devices. Schema changes ripple through `loader.py`, `card.py`/`key.py`, `verify.py`, and the test fixtures in `conftest.py`.

## Testing

- `asyncio_mode = "auto"` (set in `pyproject.toml`) — async tests need **no** `@pytest.mark.asyncio` decorator.
- All hardware is mocked. `tests/conftest.py` provides `mock_streamdeck_device`, `mock_mini_device`, `mock_neo_device`, `mock_xl_device` plus capability constants (`STREAM_DECK_MINI`, `STREAM_DECK_NEO`, `STREAM_DECK_XL`) — never require a real device.
- `.dui` test packages are built into `tmp_path` by helpers `_write_card_dui_package` / `_write_key_dui_package`; use the `card_dui_path`, `key_dui_path`, `card_package_spec`, `key_package_spec`, and `dui_packages_dir` fixtures rather than rolling your own.
- Common slot fixtures: `key_slot`, `encoder`, `touchscreen`, `page` (a `Screen` on Stream Deck+ caps), and image fixtures `sample_icon`, `sample_rgb_icon`, `sample_widget_image`.
