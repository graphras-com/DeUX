# deckboard

A high-level, asyncio-native Python library for Elgato Stream Deck+ devices.

Deckboard provides a clean, declarative API for building multi-page interfaces
with keys, encoders, and touchscreen cards on the Stream Deck+. It handles
device discovery, image rendering, icon fetching, and event dispatch so you can
focus on your application logic.

## Features

- **Async-first** -- built on `asyncio` with `async with` context manager support.
- **Multi-page UI** -- define named screens, each with their own keys, encoders, and cards.
- **Declarative icons** -- use any [Iconify](https://iconify.design/) icon by name (e.g. `mdi:home`), fetched and cached automatically.
- **Event decorators** -- register handlers with `@key.on_press`, `@encoder.on_turn`, `@card.on_tap`, etc.
- **Touchscreen cards** -- four card zones on the LCD strip, each with icon, label, and value.
- **Automatic rendering** -- dirty tracking and on-demand refresh.

## Installation

```bash
pip install deckboard
```

### System dependencies

Deckboard uses [python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck)
under the hood, which requires `libhidapi`:

```bash
# macOS
brew install hidapi cairo

# Debian / Ubuntu
sudo apt install libhidapi-libusb0 libcairo2
```

`cairo` (or `librsvg`) is needed for SVG-to-PNG icon conversion.

## Quick start

```python
import asyncio
from deckboard import Deck

async def main():
    async with Deck() as deck:
        screen = deck.screen("main")
        screen.key(0).set_icon("mdi:home").set_label("Home")

        @screen.key(0).on_press
        async def on_home():
            print("Home pressed!")

        await deck.set_screen("main")
        await deck.wait_closed()

asyncio.run(main())
```

See [`examples/`](examples/) for a full multi-page demo.

## Project structure

```
deckboard/
  src/deckboard/     # Library source
  examples/          # Usage examples
  docs/              # Documentation
  tests/             # Tests (planned)
```

## License

Apache 2.0 -- see [LICENSE](LICENSE) for details.
