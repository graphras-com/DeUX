# deckboard

An asyncio-native Python 3.11+ library for building rich interfaces on the
Elgato Stream Deck+.

Deckboard wraps the low-level HID layer and gives you a high-level API for
keys, rotary encoders, and the touchscreen strip. Define multi-screen layouts,
register event handlers with decorators, and use declarative `.dsui` packages
for SVG-based UI — the library handles rendering and device I/O.

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

The library depends on system libraries for HID access and SVG rendering.
Install them before using deckboard:

**macOS**

```bash
brew install hidapi cairo
```

**Debian / Ubuntu**

```bash
sudo apt install libhidapi-libusb0 libcairo2
```

## Features

### Async context manager

`Deck` manages the full device lifecycle. Opening, event dispatch, rendering,
and cleanup are handled automatically:

```python
async with Deck(brightness=90) as deck:
    # device is open, event loop is running
    ...
# device is closed, resources are released
```

The constructor accepts optional parameters:

| Parameter        | Default            | Description                        |
|------------------|--------------------|------------------------------------|
| `device_type`    | `"Stream Deck +"`  | Stream Deck model to search for    |
| `device_index`   | `0`                | Which device if multiple are found |
| `brightness`     | `80`               | Initial brightness (0-100)         |

### Screens

Screens are named layouts. Each screen holds up to 8 key slots, 4 encoder
slots, and 4 touchscreen card zones. Switch between screens atomically:

```python
main = deck.screen("main")
settings = deck.screen("settings")

await deck.set_screen("main")       # render and activate
await deck.set_screen("settings")   # swap instantly
```

### Keys

`KeySlot` wraps a single physical key (indices 0-7). Register press and
release handlers with decorators:

```python
@screen.key(0).on_press
async def handle_press():
    print("pressed")

@screen.key(0).on_release
async def handle_release():
    print("released")
```

For keys with custom visual content, use `.dsui` key packages (see below).

### Encoders

`EncoderSlot` wraps a rotary encoder (indices 0-3):

```python
@screen.encoder(0).on_turn
async def on_turn(direction: int):
    # positive = clockwise, negative = counter-clockwise
    print(f"turned {direction}")

@screen.encoder(0).on_press
async def on_press():
    print("encoder pushed")

@screen.encoder(0).on_release
async def on_release():
    print("encoder released")
```

### Touchscreen cards

The 800x100 touchscreen is divided into 4 card zones. Cards are subclasses of
the `Card` abstract base class. Implement `render()` to draw your content:

```python
from PIL import Image
from deckboard import Card
from deckboard.render import PANEL_WIDTH, PANEL_HEIGHT

class StatusCard(Card):
    def __init__(self, index: int):
        super().__init__(index)
        self.status = "OK"

    def render(self) -> Image.Image:
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
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

@card.on_encoder_turn
async def on_enc_turn(direction: int):
    print(f"encoder above card turned {direction}")
```

### Dirty tracking and rendering

Cards track whether they need re-rendering. After updating values
programmatically, call `refresh()` to push changes to the device:

```python
card.set("title", "Updated")
await deck.refresh()
```

## Declarative UI packages (.dsui)

For complex layouts, deckboard supports `.dsui` packages: directories
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

| Type         | Description                                   |
|--------------|-----------------------------------------------|
| `text`       | Set text content on an SVG element            |
| `image`      | Embed a PIL Image into an SVG `<image>` node  |
| `visibility` | Toggle `display` attribute of an SVG element  |
| `color`      | Set `fill` or `stroke` on an SVG element      |

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
        card = DsuiCard(0, audio_spec)
        card.set("title", "Bohemian Rhapsody")
        card.set("artist", "Queen")
        screen.set_card(0, card)

        @card.on("next")
        async def next_track():
            card.set("title", "Another One Bites the Dust")
            await deck.refresh()

        # key from .dsui
        power = DsuiKey(0, power_spec)
        power.set("ring_color", "#00ff00")
        screen.set_key(0, power)

        @power.on_event("activate")
        async def on_activate():
            print("power activated")

        await deck.set_screen("main")
        await deck.wait_closed()
```

## Preview tool

Preview SVG designs on a physical Stream Deck+ without writing application
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
  runtime/          # Device lifecycle, events, async transport
  render/           # Image rendering, SVG rasterisation
  ui/               # Screens, key slots, encoder slots, cards
  dsui/             # Declarative .dsui package system
  tools/            # CLI utilities (preview)
tests/              # Test suite (pytest, 95%+ coverage)
examples/           # Usage examples and sample .dsui packages
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

| Class          | Module                      | Description                                |
|----------------|-----------------------------|--------------------------------------------|
| `Deck`         | `deckboard.runtime.deck`    | Main entry point, device lifecycle         |
| `Screen`       | `deckboard.ui.screen`       | Named layout of keys, encoders, and cards  |
| `KeySlot`      | `deckboard.ui.controls`     | Physical key (0-7)                         |
| `EncoderSlot`  | `deckboard.ui.controls`     | Rotary encoder (0-3)                       |
| `Card`         | `deckboard.ui.cards`        | Abstract base for touchscreen cards        |
| `BlankCard`    | `deckboard.ui.cards`        | Default empty card                         |
| `TouchStrip`   | `deckboard.ui.touch_strip`  | Container for 4 card zones                 |


### DSUI classes

| Class          | Module                      | Description                                |
|----------------|-----------------------------|--------------------------------------------|
| `DsuiCard`     | `deckboard.dsui.card`       | Card backed by a .dsui package             |
| `DsuiKey`      | `deckboard.dsui.key`        | Key backed by a .dsui package              |
| `PackageSpec`  | `deckboard.dsui.schema`     | Immutable .dsui package manifest           |
| `EventMap`     | `deckboard.dsui.event_map`  | Physical-to-semantic event routing         |
| `SvgRenderer`  | `deckboard.dsui.svg_renderer` | SVG rendering with live data bindings    |

### Event types

| Class               | Fields                                             |
|---------------------|----------------------------------------------------|
| `KeyEvent`          | `key: int`, `pressed: bool`                        |
| `EncoderTurnEvent`  | `encoder: int`, `direction: int`                   |
| `EncoderPressEvent` | `encoder: int`, `pressed: bool`                    |
| `TouchEvent`        | `event_type: EventType`, `x`, `y`, `x_out`, `y_out` |

### Exceptions

| Exception      | Raised when                                |
|----------------|--------------------------------------------|
| `DeckError`       | Device not found, not opened, or HID error |
| `RasterizeError`  | SVG rasterisation failure                  |
| `PackageError`    | Invalid .dsui manifest or layout           |

## License

Apache 2.0 -- see [LICENSE](LICENSE) for details.
