# DeckUI

[![CI](https://github.com/graphras-com/DeckUI/actions/workflows/ci.yml/badge.svg)](https://github.com/graphras-com/DeckUI/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org)
[![gitleaks](https://img.shields.io/badge/protected%20by-gitleaks-blue)](https://github.com/gitleaks/gitleaks)
[![Dependabot](https://img.shields.io/badge/dependabot-enabled-brightgreen?logo=dependabot)](https://github.com/graphras-com/DeckUI/network/updates)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-online-blue)](https://graphras-com.github.io/DeckUI/)

A high-level, asyncio-native Python library for Elgato Stream Deck devices. Define screen layouts, key actions, encoder controls, and touchscreen card UIs using a declarative, event-driven API.

## Features

- Auto-discovery, hot-plug detection, and auto-reconnect via `DeckManager`
- Screen-based navigation with atomic screen switching
- Key slots with `on_press` / `on_release` decorators
- Encoder slots for rotary dial events (turn, press, hold)
- TouchStrip and InfoScreen support
- `.dui` package format: declarative touchscreen card UIs using SVG layouts + YAML manifests with data bindings
- Iconify icon integration
- Supports Stream Deck+, Mini, Neo, and XL

## Requirements

- Python 3.11+
- `libhidapi` (system dependency for USB HID communication)
- `libcairo2-dev` (for SVG rendering via CairoSVG)

## Installation

```bash
pip install deckui
```

For development:

```bash
pip install -e ".[test]"
```

## Usage

### Basic key handling

```python
import asyncio
from deckui import DeckManager

async def main():
    manager = DeckManager()

    @manager.on_connect()
    async def handle(deck):
        screen = deck.screen("main")

        @screen.key(0).on_press
        async def on_home():
            print("Home pressed!")

        await deck.set_screen("main")

    async with manager:
        await manager.wait_closed()

asyncio.run(main())
```

### Using `.dui` packages

```python
from deckui.dui import load_package, DuiCard

spec = load_package("./AudioCard.dui")
card = DuiCard(spec)
card.set("artist", "Ash Walker")

@card.on("toggle_play_pause")
async def handle():
    ...
```

## Configuration

No environment variables are required. Device capabilities are auto-detected from hardware.

`.dui` packages are configured via YAML manifests defining bindings (text, image, visibility, color, range, slider, toggle, iconify) and event mappings.

## Development

Run tests:

```bash
pytest
```

Run tests with coverage (95% threshold):

```bash
pytest --cov=deckui --cov-fail-under=95
```

Lint:

```bash
ruff check .
```

Type check:

```bash
mypy
```

## Security

- Secrets scanning via [Gitleaks](https://github.com/gitleaks/gitleaks) runs on every CI pipeline with full git history scanning
- No secrets or credentials are stored in the repository

## CI/CD

GitHub Actions orchestrates all checks via `ci.yml`:

- **Lint** -- Ruff
- **Build** -- Package build verification
- **Type check** -- mypy (strict mode)
- **Tests** -- pytest across Python 3.11, 3.12, 3.13 with 95% coverage threshold
- **Secrets scan** -- Gitleaks
- **Release** -- Triggered on `v*` tags after quality gate passes

Dependabot is enabled for weekly updates of pip and GitHub Actions dependencies.

## Contributing

Contributions are welcome. Please open an issue or pull request. This project follows the [Contributor Covenant v2.0](CODE_OF_CONDUCT.md) code of conduct.

## License

Apache-2.0 -- see [LICENSE](LICENSE).
