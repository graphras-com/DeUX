# AI_USAGE.md

> **Audience:** AI coding assistants helping developers build Stream Deck applications with DeUX.
> This file describes how to use the library correctly. For contributing to the library itself, see `AGENTS.md`.

## Core Principle

**Always use the DUI layer.** DeUX provides a declarative UI model (DUI) that separates interface definition from runtime logic. AI agents must guide developers toward `DuiCard`, `DuiKey`, `Screen`, and `DeckManager` — never toward the low-level rendering, transport, or SVG internals.

---

## The DUI Approach

A `.dui` package is a directory (e.g. `AudioCard.dui/`) containing:

- **`manifest.yaml`** — declares bindings (data contract), events (input mapping), regions (touch areas), and spinner config.
- **SVG layout file** — the visual template. Elements are referenced by `id` and styled with theme CSS classes.
- **`assets/`** (optional) — static images and custom spinner frames.

Python code only handles application logic: setting binding values, responding to semantic events, and managing reactive data sources.

---

## Recommended API Surface

All entry points are importable from `deux` directly.

### DUI Components

| Entry Point | Purpose |
|---|---|
| `DuiCard("Name")` | Touchscreen card from a `.dui` package |
| `DuiKey("Name")` | Physical key from a `.dui` package |

### Card / Key Data API

| Method | Description |
|---|---|
| `.set(name, value)` | Set a single binding value |
| `.set_many(**kwargs)` | Set multiple bindings at once |
| `.set_range(name, value, min_val, max_val)` | Set a range/slider binding |
| `.adjust_range(name, delta)` | Increment/decrement a range binding |
| `.get(name)` | Read current binding value |

### Card / Key Event API

| Method | Description |
|---|---|
| `@card.on("event_name")` | Decorator to handle a semantic event (cards) |
| `@key.on_event("event_name")` | Decorator to handle a semantic event (keys) |
| `.bind_event(name, handler)` | Programmatic event binding |
| `.forward(event_name, coroutine)` | Forward an event directly to an async function |

### Reactive Binding

| Method | Description |
|---|---|
| `.bind(name, async_event, transform=...)` | Auto-update a binding when an `AsyncEvent` fires |
| `.bind_range(name, async_event, min_val, max_val)` | Reactive range binding |
| `.bind_many(async_event, **transforms)` | Bind multiple values from one event source |

### Busy State

| Method | Description |
|---|---|
| `.start_busy()` | Show spinner animation |
| `.finish_busy()` | Stop spinner animation |

### Package Discovery

| Function | Description |
|---|---|
| `add_dui_path("~/my-packages")` | Register a custom package search directory (highest priority) |
| `remove_dui_path(path)` | Unregister a search directory |
| `list_dui_packages()` | List all discoverable package names |
| `resolve_dui("Name")` | Resolve a name to a `PackageSpec` |
| `load_package("./Foo.dui")` | Load a `.dui` directory by path |
| `load_all_packages(dir)` | Load all `.dui` packages from a directory |
| `clear_dui_cache()` | Force re-read from disk on next resolve |

---

## DeckManager

`DeckManager` handles device discovery, hot-plugging, and multi-deck orchestration.

### Setup

```python
from deux import DeckManager

manager = DeckManager(poll_interval=2.0, brightness=80)

@manager.on_connect()
async def on_any_device(deck):
    # Set up screens, cards, keys here
    ...

@manager.on_disconnect
async def on_lost(info):
    print(f"Lost {info.serial_number}")

await manager.start()
await manager.wait_closed()  # blocks until stop() is called
```

Or as an async context manager:

```python
async with manager:
    await manager.wait_closed()
```

### Filtered Connect Handlers

```python
@manager.on_connect(deck_type="Stream Deck XL")
async def xl_setup(deck):
    ...

@manager.on_connect(serial="AB12CD34")
async def specific_device(deck):
    ...
```

### Critical Behaviors

1. **No state preservation on disconnect.** When a device disconnects, the `Deck` instance is destroyed. On reconnection, `on_connect` fires again with a **fresh** `Deck`. You must rebuild all UI (screens, cards, keys) in your `on_connect` handler. Treat every connect as initial setup.

2. **First-match-wins for connect handlers.** Only the first handler whose filters match is called. Registration order matters. Place specific filters (by serial or deck type) before catch-all handlers.

3. **Single disconnect handler.** Unlike connect (which supports multiple filtered handlers), only one `on_disconnect` handler can be active. The last one registered wins.

4. **Reconnection is automatic.** A device that reappears after disconnection is treated as a new connection — `on_connect` fires again. There is no separate "reconnect" event.

5. **Errors in handlers are logged, not fatal.** If a connect or disconnect handler raises, the exception is logged and the manager continues running. The device remains managed even if the handler fails.

### Multi-Deck Pattern

```python
@manager.on_connect(deck_type="Stream Deck XL")
async def setup_xl(deck):
    screen = Screen(...)
    # XL-specific layout
    ...

@manager.on_connect(deck_type="Stream Deck +")
async def setup_plus(deck):
    screen = Screen(...)
    # Plus-specific layout with touchscreen cards
    ...

@manager.on_connect()
async def setup_fallback(deck):
    # Generic setup for any other device
    ...
```

---

## Theming

DeUX generates a full 18-colour palette from a single primary RGB colour. Themes are applied via CSS classes in SVG layouts.

### Creating Themes

```python
from deux import Theme, set_active_theme

# Default theme (blue primary)
theme = Theme.default()

# Custom colour
theme = Theme.from_color(200, 50, 80, font_family="JetBrains Mono")

# Random theme
theme = Theme.from_random()
```

### Applying Themes

Themes cascade with three levels of specificity (most specific wins):

| Level | How to set | Scope |
|---|---|---|
| System | `set_active_theme(theme)` | All decks and screens (global default) |
| Deck | `deck.theme = theme` | All screens on that deck |
| Screen | `screen.theme = theme` | That screen only |

```python
# System-wide
set_active_theme(Theme.from_color(200, 50, 80))

# Per-deck override
deck.theme = Theme.from_color(50, 180, 100)

# Per-screen override
screen.theme = Theme.from_random()

# Reset system theme to default
set_active_theme(None)
```

### Palette Classes

The generated palette provides 18 CSS classes usable in SVG layouts:

| Class | Role |
|---|---|
| `background-dark` / `background-light` | Background tones |
| `border-primary` / `border-secondary` | Border colours |
| `text-primary` | Main text |
| `text-secondary` | Secondary text (the primary colour itself) |
| `text-selected` | Selected/highlighted text |
| `text-accent` | Accent text (analogous hue) |
| `text-muted` | Muted/disabled text |
| `text-fancy` | Decorative text (complementary hue) |
| `icon` / `icon-active` / `icon-inactive` | Icon states |
| `sliders` / `dynamic` | Interactive element colours |
| `success` / `warning` / `error` | Status colours |

SVG elements reference these with `class="text-primary"`, etc. The theme CSS sets the `color` property for each class.

### Theme and Bindings Interaction

- **`color` bindings** override theme colours on specific elements (via `fill`, `stroke`, or `color` attributes directly on the SVG node).
- **`css_class` bindings** dynamically switch an element's CSS class, changing which theme palette colour it uses.
- **`list` bindings** can reference theme classes in `active_attrs` / `inactive_attrs` (e.g. `{ class: "text-selected" }` vs `{ class: "text-muted" }`).

---

## Binding Types Reference

Manifests declare bindings in `manifest.yaml` under the `bindings` key. Each binding maps a named Python value to an SVG element mutation.

| Type | Effect |
|---|---|
| `text` | Update text content of an SVG element |
| `image` | Replace or insert an image (base64 data URI) |
| `visibility` | Show/hide an element |
| `color` | Set `fill`, `stroke`, or `color` attribute |
| `range` | Horizontal progress/level bar (clips a node) |
| `slider` | Positioned indicator along a track |
| `toggle` | Binary state with distinct visual representations |
| `iconify` | Fetch and embed an icon from Iconify API |
| `list` | Render a list with active/inactive styling |
| `transform` | Apply SVG transform (translate, rotate, scale) |
| `css_class` | Dynamically assign a CSS class |

---

## Event Sources Reference

Events in `manifest.yaml` map physical hardware inputs to named semantic events.

| Source | Hardware Input |
|---|---|
| `key_press` | Key pressed down |
| `key_release` | Key released |
| `key_press_release` | Full press-then-release gesture |
| `key_hold` | Key held for a duration (configurable timer) |
| `encoder_press` / `encoder_release` | Encoder button pressed / released |
| `encoder_press_release` | Full encoder press-then-release gesture |
| `encoder_hold` | Encoder button held |
| `encoder_turn` | Encoder rotated (with direction filtering and accumulation) |
| `encoder_press_turn` | Encoder rotated while pressed |
| `tap` | Touchscreen tap (within a defined region) |
| `long_press` | Touchscreen long press |

---

## Typical Usage Example

```python
from deux import DuiCard, DuiKey, DeckManager, Screen, Theme, set_active_theme

set_active_theme(Theme.from_color(39, 87, 179))

manager = DeckManager()

@manager.on_connect(deck_type="Stream Deck +")
async def setup(deck):
    card = DuiCard("AudioCard")
    card.set("artist", "Ash Walker")
    card.set("track", "Aquamarine")
    card.set_range("volume", 75, min_val=0, max_val=100)

    @card.on("toggle_play_pause")
    async def handle_play():
        ...

    @card.on("volume_change")
    async def handle_volume(value):
        card.adjust_range("volume", value)

    key = DuiKey("PowerKey")
    key.set("label", "Power")

    @key.on_event("activate")
    async def handle_power():
        ...

    screen = Screen(...)
    screen.set_card(0, card)
    screen.set_key(0, key)
    deck.set_screen(screen)

await manager.start()
await manager.wait_closed()
```

---

## What NOT to Use

The following are internal implementation details. Never suggest these to developers:

| Module | Internal Components |
|---|---|
| `deux.dui.svg_renderer` | `SvgRenderer` — SVG template engine |
| `deux.dui.event_map` | `EventMap` — physical-to-semantic event router |
| `deux.dui.spinner` | `SpinnerFrames` — spinner frame pre-rendering |
| `deux.dui.animator` | `SpinnerAnimator` — frame loop |
| `deux.dui.iconify` | `fetch_icon` — raw Iconify API client |
| `deux.render.svg_rasterize` | `_svg_to_png`, `_rasterize_svg`, `compose_svg_layers`, etc. |
| `deux.render.key_renderer` | `render_key_image`, `render_blank_key`, `_encode_image` |
| `deux.render.touch_renderer` | `compose_touchstrip`, `render_blank_touchscreen` |
| `deux.render.screen_renderer` | `render_info_screen` |
| `deux.runtime.transport` | `AsyncTransport` — low-level HID wrapper |
| `deux.runtime.discovery` | `list_devices` — raw device enumeration |
| `deux.runtime.capabilities` | `DeviceCapabilities` — hardware descriptors |
| `deux.ui.controls` | `KeySlot`, `EncoderSlot` — base classes (use `DuiKey`) |
| `deux.ui.cards` | `Card`, `BlankCard` — base classes (use `DuiCard`) |
| `deux.ui.controls.dial_accumulator` | `DialAccumulator` — encoder internals |
