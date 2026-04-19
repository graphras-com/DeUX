# Deckboard

An asyncio-native Python 3.11+ library for building rich interfaces on
Elgato Stream Deck devices.

Deckboard auto-detects your connected Stream Deck and adapts to its hardware
capabilities — key count, key image size, encoders, touchscreen, and info
screen. Define multi-screen layouts, register event handlers with decorators,
and use declarative `.dsui` packages for SVG-based UI. The library handles
rendering, encoding, and device I/O.

## Supported devices

| Device | Keys | Key size | Encoders | Touchscreen | Info screen | Image format |
|--------|------|----------|----------|-------------|-------------|--------------|
| Mini | 6 (3×2) | 80×80 | — | — | — | BMP |
| Original v1 | 15 (5×3) | 72×72 | — | — | — | BMP |
| Original v2 | 15 (5×3) | 72×72 | — | — | — | JPEG |
| XL | 32 (8×4) | 96×96 | — | — | — | JPEG |
| **Plus** | 8 (4×2) | 120×120 | 4 | 800×100 | — | JPEG |
| Neo | 8 (4×2) | 96×96 | — | — | 248×58 | JPEG |

The Pedal is excluded — it has no visual output.

## Quick start

```python
import asyncio
from deckboard import Deck, DsuiKey, load_package

async def main():
    async with Deck() as deck:
        screen = deck.screen("main")

        @screen.key(0).on_press
        async def on_home():
            print("Home pressed!")

        # encoders are only available on devices that have them (e.g. Plus)
        if deck.capabilities.has_encoders:
            @screen.encoder(0).on_turn
            async def on_turn(direction: int):
                print(f"Encoder turned: {direction}")

        await deck.set_screen("main")
        await deck.wait_closed()

asyncio.run(main())
```

## Installation

```bash
pip install deckboard
```

Deckboard depends on system libraries for HID access and SVG rendering.
Install them before using Deckboard:

**macOS**

```bash
brew install hidapi cairo
```

**Debian / Ubuntu**

```bash
sudo apt install libhidapi-libusb0 libcairo2
```

## Features

### Auto-detection

`Deck()` discovers and connects to the first available visual Stream Deck.
All layout sizes, image formats, and rendering parameters adapt automatically
based on a `DeviceCapabilities` snapshot queried from the hardware.

```python
async with Deck() as deck:
    print(deck.capabilities.deck_type)      # e.g. "Stream Deck XL"
    print(deck.capabilities.key_count)      # e.g. 32
    print(deck.capabilities.key_size)       # e.g. (96, 96)
    print(deck.capabilities.has_encoders)   # e.g. False
    print(deck.capabilities.has_touchscreen)  # e.g. False
```

Constructor parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `serial_number` | `None` | Target a specific device by serial number |
| `device_index` | `0` | Which device if multiple visual decks are found |
| `brightness` | `80` | Initial brightness (0–100) |

### Screens

Screens are named layouts. Each screen holds key slots, encoder slots (if the
device has encoders), and touchscreen card zones (if the device has a
touchscreen). Counts adapt to the connected hardware.

```python
main = deck.screen("main")
settings = deck.screen("settings")

await deck.set_screen("main")       # render and activate
await deck.set_screen("settings")   # swap instantly
```

### Keys

`KeySlot` wraps a single physical key. The valid index range depends on the
device (0–5 for Mini, 0–7 for Plus/Neo, 0–14 for Original, 0–31 for XL).

```python
@screen.key(0).on_press
async def handle_press():
    print("pressed")

@screen.key(0).on_release
async def handle_release():
    print("released")
```

### Encoders

`EncoderSlot` wraps a rotary encoder. Only available on devices with dials
(currently the Plus with 4 encoders).

```python
@screen.encoder(0).on_turn
async def on_turn(direction: int):
    # positive = clockwise, negative = counter-clockwise
    print(f"turned {direction}")

@screen.encoder(0).on_press
async def on_press():
    print("encoder pushed")
```

### Touchscreen cards

On devices with a touchscreen (currently the Plus, 800×100), the strip is
divided into card zones matching the encoder count. Cards are subclasses of
the `Card` abstract base class:

```python
from PIL import Image
from deckboard import Card

class StatusCard(Card):
    def __init__(self, index: int):
        super().__init__(index)
        self.status = "OK"

    def render(self) -> Image.Image:
        img = Image.new("RGB", (200, 100), "black")
        # draw status text, icons, etc.
        return img

screen.set_card(0, StatusCard(0))
```

Cards support touch and encoder event decorators:

```python
card = screen.card(0)

@card.on_tap
async def on_tap():
    print("card tapped")

@card.on_long_press
async def on_long():
    print("long press")

@card.on_drag
async def on_drag(x, y, x_out, y_out):
    print(f"drag from ({x},{y}) to ({x_out},{y_out})")
```

### Info screen (Neo)

The Neo has a 248×58 non-touch info display. Deckboard exposes it via the
`InfoScreen` class with simple dirty-tracked image management:

```python
from PIL import Image

async with Deck() as deck:
    if deck.capabilities.has_info_screen:
        screen = deck.screen("main")
        info = screen.info_screen

        img = Image.new("RGB", (248, 58), "black")
        # draw status content...
        info.set_image(img)
        await deck.refresh()
```

### Dirty tracking and rendering

Cards, keys, and the info screen track whether they need re-rendering. After
updating values programmatically, call `refresh()` to push changes to the
device:

```python
card.set("title", "Updated")
await deck.refresh()
```

## Declarative UI packages (.dsui)

For complex layouts, Deckboard supports `.dsui` packages: directories
containing a YAML manifest and an SVG layout. The SVG is rendered with live
data bindings and the manifest maps physical events to semantic handlers.

### Package structure

```
AudioCard.dsui/
  manifest.yaml
  layout.svg
  assets/          # optional binary assets
```

### manifest.yaml

```yaml
name: AudioCard
type: TouchStripCard    # or "Key"
version: 1
layout: layout.svg

bindings:
  title:
    type: text
    node: title_text
  cover:
    type: image
    node: cover_img
    fit: cover
  progress_color:
    type: color
    node: progress_bar
    attribute: fill
    default: "#f2b23a"

events:
  - name: next
    source: encoder_turn
    direction: right
  - name: toggle_play_pause
    source: encoder_press_release
    max_duration_ms: 250

regions:
  - name: card
    x: 0
    y: 0
    width: 197
    height: 98
    events: [tap, long_press]
```

### Binding types

| Type | Description |
|------|-------------|
| `text` | Set text content on an SVG element |
| `image` | Embed a PIL Image into an SVG `<image>` node |
| `visibility` | Toggle `display` attribute of an SVG element |
| `color` | Set `fill` or `stroke` on an SVG element |

### Event sources

`encoder_press`, `encoder_release`, `encoder_press_release`, `encoder_turn`,
`encoder_press_turn`, `key_press`, `key_release`, `key_press_release`, `tap`,
`long_press`

### Using .dsui packages

```python
from deckboard import Deck, DsuiCard, DsuiKey, load_package

async def main():
    async with Deck() as deck:
        audio_spec = load_package("AudioCard.dsui")
        power_spec = load_package("PowerKey.dsui")

        screen = deck.screen("main")

        # touchscreen card from .dsui
        card = DsuiCard(audio_spec)
        card.set("title", "Bohemian Rhapsody")
        card.set("artist", "Queen")
        screen.set_card(0, card)

        @card.on("next")
        async def next_track():
            card.set("title", "Another One Bites the Dust")
            await deck.refresh()

        # key from .dsui
        power = DsuiKey(power_spec)
        power.set("ring_color", "#00ff00")
        screen.set_key(0, power)

        @power.on_event("activate")
        async def on_activate():
            print("power activated")

        await deck.set_screen("main")
        await deck.wait_closed()
```

## Preview tool

Preview SVG designs on a physical Stream Deck without writing application
code:

```bash
python -m deckboard.tools.preview \
    --key0 power_button.svg \
    --card0 media_card.svg \
    --card1 status_card.svg \
    --brightness 90 \
    --background "#1a1a2e"
```

Arguments: `--key0` through `--key7`, `--card0` through `--card3`,
`-b/--brightness`, `--background`, `-v/--verbose`. Press Ctrl+C to exit.

## Project structure

```
src/deckboard/
  runtime/          # Device lifecycle, capabilities, events, async transport
  render/           # Image rendering, SVG rasterisation, info screen rendering
  ui/               # Screens, key slots, encoder slots, cards, info screen
  dsui/             # Declarative .dsui package system
  tools/            # CLI utilities (preview)
tests/              # Test suite (pytest, 95%+ coverage)
```

## Development

```bash
# install in editable mode with test dependencies
pip install -e ".[test]"

# run the full test suite
python -m pytest tests/ --cov=deckboard --cov-report=term-missing --cov-fail-under=95

# lint
ruff check src/ tests/

# type check
mypy src/deckboard/
```

## API reference

### Core classes

| Class | Module | Description |
|-------|--------|-------------|
| `Deck` | `deckboard.runtime.deck` | Main entry point, auto-detects device |
| `DeviceCapabilities` | `deckboard.runtime.capabilities` | Frozen snapshot of device hardware |
| `RenderMetrics` | `deckboard.render.metrics` | Computed rendering dimensions and margins |
| `Screen` | `deckboard.ui.screen` | Named layout of keys, encoders, and cards |
| `KeySlot` | `deckboard.ui.controls` | Physical key (index range varies by device) |
| `EncoderSlot` | `deckboard.ui.controls` | Rotary encoder (Plus only) |
| `Card` | `deckboard.ui.cards` | Abstract base for touchscreen cards |
| `BlankCard` | `deckboard.ui.cards` | Default empty card |
| `TouchStrip` | `deckboard.ui.touch_strip` | Container for touchscreen card zones |
| `InfoScreen` | `deckboard.ui.info_screen` | Non-touch info display (Neo) |

### DSUI classes

| Class | Module | Description |
|-------|--------|-------------|
| `DsuiCard` | `deckboard.dsui.card` | Card backed by a .dsui package |
| `DsuiKey` | `deckboard.dsui.key` | Key backed by a .dsui package |
| `PackageSpec` | `deckboard.dsui.schema` | Immutable .dsui package manifest |
| `EventMap` | `deckboard.dsui.event_map` | Physical-to-semantic event routing |
| `SvgRenderer` | `deckboard.dsui.svg_renderer` | SVG rendering with live data bindings |

### Event types

| Class | Fields |
|-------|--------|
| `KeyEvent` | `key: int`, `pressed: bool` |
| `EncoderTurnEvent` | `encoder: int`, `direction: int` |
| `EncoderPressEvent` | `encoder: int`, `pressed: bool` |
| `TouchEvent` | `event_type: EventType`, `x`, `y`, `x_out`, `y_out` |

### Exceptions

| Exception | Raised when |
|-----------|-------------|
| `DeckError` | Device not found, not opened, or HID error |
| `RasterizeError` | SVG rasterisation failure |
| `PackageError` | Invalid .dsui manifest or layout |

## Acknowledgments

Deckboard is built on these excellent open-source libraries:

- **[python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck)** — Low-level HID interface for Stream Deck devices (MIT)
- **[Pillow](https://github.com/python-pillow/Pillow)** — Image processing and rendering (HPND)
- **[CairoSVG](https://github.com/Kozea/CairoSVG)** — SVG-to-PNG rasterisation (LGPL-3.0)
- **[PyYAML](https://github.com/yaml/pyyaml)** — YAML parsing for .dsui manifests (MIT)

See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) for full license texts.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
