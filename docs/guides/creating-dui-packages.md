# Creating DUI Packages

A `.dui` package is a self-contained directory that declaratively defines a Stream Deck UI — either a touchscreen card or a physical key — using an SVG layout, a YAML manifest, and optional image assets. No Python rendering code required.

> Looking for the packages bundled with DeUX (`IconKey`, `PictureKey`, `DashboardCard`) or for how `DuiKey("name")` resolves to a package? See the [DUI Repository & Built-in Packages](dui-repository.md) guide.

## Package Structure

```
MyPackage.dui/
  manifest.yaml      # Required – metadata, bindings, events, regions
  layout.svg          # Required – SVG layout template
  assets/             # Optional – static images (PNG, JPEG, etc.)
    icon.png
```

## The Manifest

`manifest.yaml` is the heart of every package. It has four required top-level fields, optional metadata for repository publishing, and three optional sections for bindings, events, and regions.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Package name (non-empty) |
| `type` | `str` | `"TouchStripCard"` (touchscreen panel) or `"Key"` (physical key) |
| `version` | `int` | Positive integer (>= 1) |
| `layout` | `str` | Relative path to the SVG file (e.g. `layout.svg`) |

### Metadata Fields

These fields are optional for local use but required when publishing to a DUI package repository. The `verify --strict` tool enforces `description` and `author`.

| Field | Type | Required for repo | Description |
|-------|------|:-----------------:|-------------|
| `description` | `str` | yes | One-line summary for search and display |
| `author` | `str` | yes | Author name and optional email (`"Jane Doe <jane@example.com>"`) |
| `license` | `str` | no | SPDX license identifier (`MIT`, `Apache-2.0`, `CC-BY-4.0`) |
| `tags` | `list[str]` | no | Free-form lowercase labels for search (`[music, media, spotify]`) |
| `category` | `str` | no | Primary category from a controlled vocabulary (see below) |
| `url` | `str` | no | Project or source URL |
| `icon` | `str` | no | Path to a thumbnail in `assets/` for repository listings |
| `min_deux` | `str` | no | Minimum DeUX version required (e.g. `"0.5.0"`) |
| `device` | `list[str]` | no | Explicit device compatibility (`[StreamDeckPlus, StreamDeckXL]`) |

#### Valid Categories

`media` · `productivity` · `system` · `gaming` · `social` · `development` · `utilities` · `streaming` · `home-automation` · `communication`

### Optional Sections

| Section | Description |
|---------|-------------|
| `bindings` | Data bindings that connect values to SVG elements |
| `events` | Map physical inputs to named semantic events |
| `regions` | Touchscreen hit-test areas (TouchStripCard only) |

### Minimal Example

```yaml
name: HelloKey
type: Key
version: 1
layout: layout.svg

bindings:
  label:
    type: text
    node: label
    default: "Hello"
```

### Repository-Ready Example

```yaml
name: NowPlaying
type: TouchStripCard
version: 2
layout: layout.svg
description: "Media player card with album art, progress bar, and transport controls"
author: "Jane Doe <jane@example.com>"
license: MIT
category: media
tags: [music, spotify, media-player]
url: https://github.com/jane/nowplaying-dui
icon: assets/icon.png
min_deux: "0.5.0"

bindings:
  title:
    type: text
    node: title
    default: "No Track"
    max_width: 90
    overflow: ellipsis
```

---

## SVG Layout

The SVG file is a standard SVG document. Key rules:

- The root `<svg>` must have explicit `width` and `height` attributes.
- Every element referenced by a binding must have a unique `id` attribute.
- Standard dimensions:
  - **Touchscreen card**: 197 × 98 px
  - **Key**: 120 × 120 px

### Example Key SVG

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">
  <rect width="120" height="120" fill="#1a1a2e"/>
  <text id="label" x="60" y="68" text-anchor="middle"
        font-size="16" fill="white">Hello</text>
  <rect id="indicator" x="10" y="100" width="100" height="6"
        rx="3" fill="#333333"/>
</svg>
```

### Assets

Files in the `assets/` directory are loaded into memory and inlined as base64 data URIs at render time. Reference them in your SVG with `href="assets/filename.png"` on `<image>` elements.

---

## Bindings

Bindings connect runtime data to SVG elements. Each binding has a name (the key in the `bindings` map), a `type`, and a `node` (the SVG element ID to target).

### text

Bind a string value to a `<text>` element.

```yaml
title:
  type: text
  node: title
  default: "Untitled"
  max_width: 90        # optional – truncate beyond this pixel width
  overflow: ellipsis   # "ellipsis" (default) or "clip"
  wrap: false          # optional – enable word-wrapping
  max_height: 40       # optional – vertical budget for wrapped text (requires wrap)
  line_height: 14.0    # optional – line spacing in px (requires wrap)
```

If `wrap: true`, then `max_width` is required. Text is wrapped into `<tspan>` elements using pixel-accurate font metrics.

### image

Bind a PIL Image or raw bytes to an `<image>` element.

```yaml
cover:
  type: image
  node: cover
  fit: cover               # "cover" (default), "contain", or "fill"
  placeholder_node: placeholder  # optional – shown when image is None
```

### visibility

Toggle an element's display.

```yaml
overlay_visible:
  type: visibility
  node: overlay
  default: true
```

### color

Set a color attribute on an element.

```yaml
accent_color:
  type: color
  node: accent
  attribute: fill    # "fill" (default), "stroke", or "color"
  default: "#ff0000"
```

### range

Scale an element's width or height proportionally to a 0–1 value. Useful for progress bars.

```yaml
progress:
  type: range
  node: progress_bar
  default: 0.0
  direction: horizontal  # "horizontal" (default) or "vertical"
```

### slider

Translate an element's position proportionally to a 0–1 value.

```yaml
knob:
  type: slider
  node: knob
  default: 0.5
  direction: horizontal
  min_pos: 10.0    # required – position at value 0.0
  max_pos: 180.0   # required – position at value 1.0
```

### toggle

Switch visibility between two elements based on a boolean.

```yaml
play_pause:
  type: toggle
  node_on: icon_pause    # shown when truthy
  node_off: icon_play    # shown when falsy
  default: false
```

> **Note**: `toggle` uses `node_on`/`node_off` instead of `node`.

### iconify

Embed an [Iconify](https://iconify.design/) icon into a `<g>` element.

```yaml
status_icon:
  type: iconify
  node: icon_group
  size: 24           # required – icon size in px
  default: "line-md:home"
```

Icons are fetched from the Iconify API and cached in-process.

### list

Render a dynamic list of items as repeated child elements of a parent SVG node (typically a `<text>` element).
Each item is either a plain text label or an Iconify icon reference (prefix with `icon:`).
The item at `default_index` receives `active_attrs`; all others receive `inactive_attrs`.

```yaml
nav:
  type: list
  node: pager                # ID of the parent SVG element
  child_tag: tspan           # SVG element generated per item (default "tspan")
  default_items:             # initial list of labels (default [])
    - Main
    - Settings
    - "icon:mdi:home"        # prefix with "icon:" to render an Iconify icon
  default_index: 0           # active item index; use null or -1 for "no active item"
  active_attrs:              # attributes applied to the active item
    fill: "#ffffff"
    font-weight: bold
  inactive_attrs:            # attributes applied to all inactive items
    fill: "#888888"
  separator: " · "           # inserted between items; empty string disables (default)
  icon_size: 14              # pixel size for "icon:" items (default 16)
```

Runtime updates may provide a partial payload (`{"items": [...]}` or `{"index": N}`); the other half is preserved.
An index of `-1` is normalised to `None` (no active item).
Setting `items` without `index` clamps the existing index to the new bounds.

### transform

Apply one or more SVG transforms to a node proportional to a 0–1 value.
The only currently supported `kind` is `rotate`, which interpolates linearly between two angles.
Multiple transforms in the list are composed (space-separated) in order.

```yaml
gauge:
  type: transform
  node: needle
  default: 0.0               # initial normalised value (0.0–1.0)
  transforms:
    - kind: rotate
      from: -90              # angle in degrees when value is 0.0 (default 0)
      to: 90                 # angle in degrees when value is 1.0 (default 360)
      origin: center         # "center" (default) or an explicit "x y" pair
```

`origin: center` resolves to the element's bounding box center at render time.
Providing an explicit `"x y"` string (e.g. `"60 60"`) sets a fixed origin in SVG user-space coordinates.
The `transforms` list must be non-empty.

### css_class

Bind a CSS class string to an SVG element's `class` attribute.
The binding replaces the entire `class` attribute on the target node; setting an empty string removes the attribute.

```yaml
style:
  type: css_class
  node: card
  default: ""                # initial class value (default "")
```

This is useful when the layout SVG embeds a `<style>` block and you want to switch between named visual states (e.g. `default: "muted"` then update to `"active"` at runtime).

---

## Events

Events map physical hardware inputs to named semantic actions. Define them as a list under the `events` key.

```yaml
events:
  - name: activate
    source: key_press_release
    max_duration_ms: 300

  - name: hold
    source: key_hold
    hold_ms: 500
```

### Event Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Unique semantic name |
| `source` | `str` | yes | Physical input source (see table below) |
| `direction` | `str` | no | `"left"` or `"right"` (turn events only) |
| `max_duration_ms` | `int` | no | Max press duration for `*_press_release` (default 500) |
| `hold_ms` | `int` | no | Hold threshold for `*_hold` (default 500) |
| `accumulate` | `bool` | no | Debounce rapid ticks via `DialAccumulator` (turn events only, default `false`) |
| `accumulate_delay` | `float` | no | Seconds to wait after last tick before flushing (default 0.25, requires `accumulate: true`) |
| `accumulate_max_steps` | `int` | no | Cap on accumulated ticks (default 10, requires `accumulate: true`) |
| `busy` | `bool` | no | Enable spinner animation and event suppression (default `false`) |

### Sources

**Key sources** (for `type: Key`):

| Source | Fires when |
|--------|------------|
| `key_press` | Key pressed down |
| `key_release` | Key released (always) |
| `key_press_release` | Released within `max_duration_ms` (suppressed if hold fired) |
| `key_hold` | Held for `hold_ms` |

**Encoder sources** (for `type: TouchStripCard`):

| Source | Fires when |
|--------|------------|
| `encoder_press` | Encoder pressed down |
| `encoder_release` | Encoder released (always) |
| `encoder_press_release` | Released within `max_duration_ms` (suppressed if hold fired) |
| `encoder_turn` | Encoder rotated **while not pressed**; filter with `direction` |
| `encoder_press_turn` | Rotated **while pressed**; filter with `direction` |
| `encoder_hold` | Held for `hold_ms` |

`encoder_turn` and `encoder_press_turn` are mutually exclusive at runtime. While the encoder is pressed, only `encoder_press_turn` mappings are eligible — turning a pressed encoder will never fire `encoder_turn`, even if no `encoder_press_turn` is declared (or its `direction` filter doesn't match). Any turn while pressed cancels a pending `encoder_hold`.

After releasing the encoder following a press cycle that included at least one turn, plain `encoder_turn` events are suppressed for a short grace window (150 ms by default). This debounces the very common ergonomic mistake of letting a finger continue to nudge the dial while lifting off, so a `press_turn` gesture cannot accidentally bleed into an unrelated `encoder_turn` handler. Releases without an intervening turn — and `encoder_press_turn` events themselves — are never suppressed.

**Touch sources** (for regions):

| Source | Fires when |
|--------|------------|
| `tap` | Touch tap on a region |
| `long_press` | Long press on a region |

### Accumulated Turns

By default, each encoder tick fires the handler once. For continuous controls like volume or brightness, rapid ticks produce many individual calls. The `accumulate` option debounces rapid ticks and flushes them as a single callback with the net step count.

```yaml
events:
  - name: brightness_up
    source: encoder_turn
    direction: right
    accumulate: true
    accumulate_delay: 0.2       # optional – seconds before flush (default 0.25)
    accumulate_max_steps: 5     # optional – cap on net ticks (default 10)

  - name: brightness_down
    source: encoder_turn
    direction: left
    accumulate: true

  - name: kelvin_up
    source: encoder_press_turn
    direction: right
    accumulate: true
    accumulate_delay: 0.1
    accumulate_max_steps: 5
```

The handler receives a single `int` argument — the net accumulated steps (positive for right, negative for left):

```python
@card.on("brightness_up")
async def handle(steps: int):
    # steps is e.g. 3 if the user turned right 3 ticks quickly
    new_val = card.adjust_range("brightness", steps * 5, min_val=0, max_val=100)
```

**Validation rules:**

- `accumulate` is only valid on `encoder_turn` and `encoder_press_turn` sources
- `accumulate_delay` and `accumulate_max_steps` require `accumulate: true`
- `accumulate_delay` must be a positive number
- `accumulate_max_steps` must be a positive integer

---

## Regions (TouchStripCard Only)

Regions define rectangular touch-sensitive areas on the touchscreen.

```yaml
regions:
  album_art:
    x: 0
    y: 0
    width: 98
    height: 98
    events: [tap, long_press]

  controls:
    x: 98
    y: 0
    width: 99
    height: 98
    events: [tap]
```

All coordinates are non-negative integers. The `events` list is optional and restricts which touch gestures the region responds to.

---

## Spinner & Busy State

When an event handler takes time to complete (e.g. making an API call), users get no immediate visual feedback and may press the button again. The **spinner** system solves this by letting your application explicitly enter and exit a busy state with a visual animation.

### Defining a Spinner

Add a `spinner` section to your manifest:

```yaml
spinner:
  type: rotation        # "rotation", "pulse", or "custom"
  node: spinner_icon    # SVG element ID to animate (required for rotation/pulse)
  frames: 12            # frames per cycle (default 12, minimum 2)
  interval_ms: 80       # ms between frames (default 80, minimum 10)
```

Your SVG must include an element with the spinner node ID. It's typically hidden by default and made visible during animation:

```xml
<rect id="spinner_icon" x="80" y="30" width="30" height="30"
      display="none" fill="#ffffff"/>
```

### Spinner Types

#### `rotation`

Rotates the SVG node by `360/frames` degrees each frame around its centre. Good for loading spinners.

```yaml
spinner:
  type: rotation
  node: spinner_icon
  frames: 12
  interval_ms: 80
```

#### `pulse`

Cycles the node's opacity between 0.2 and 1.0 in a triangle wave. Good for subtle "working" indicators.

```yaml
spinner:
  type: pulse
  node: spinner_glow
  frames: 8
  interval_ms: 100
```

#### `custom`

Use your own pre-rendered frames. Place them in one of two formats:

**Numbered PNGs** in `assets/spinner/`:

```
MyPackage.dui/
  assets/
    spinner/
      frame_00.png
      frame_01.png
      frame_02.png
      ...
```

**Animated GIF** at `assets/spinner.gif`:

```
MyPackage.dui/
  assets/
    spinner.gif
```

For custom spinners, the `node` field is optional (ignored).

```yaml
spinner:
  type: custom
  interval_ms: 60
```

### How It Works

The busy state is **entirely controlled by your application** via two methods:

- `await card.start_busy()` / `await key.start_busy()` — enters the busy state and starts the spinner animation
- `await card.finish_busy()` / `await key.finish_busy()` — stops the spinner and exits the busy state

When busy:

1. Spinner frames are rendered **on top of the current UI state** — all bindings (text, colors, images, etc.) are preserved. Only the spinner node is animated; the rest of the key/card looks exactly as it did before.
2. For touchscreen cards, only the affected panel region is updated (not the entire strip)
3. The normal refresh cycle skips animating slots to avoid overwriting frames
4. Frames are re-generated each time the spinner starts so they always reflect the latest binding values

Duplicate `start_busy()` calls while already busy are no-ops.
`finish_busy()` when not busy is also a no-op.

### Controlling the Busy Lifecycle

Your application decides when to start and stop the spinner. This
decouples the spinner from the event handler — the handler can return
immediately while the spinner keeps running until an external signal
arrives.

```python
@key.on("toggle")
async def handle():
    await key.start_busy()
    # Fire the API call. The spinner keeps running
    # after this handler returns.
    await smart_home_api.toggle_light()

# Later, when the external system confirms the new state:
async def on_state_update(new_state):
    key.set("status_color", "#00ff00" if new_state else "#333333")
    await key.finish_busy()   # stops the spinner and re-renders
```

If the work completes within the handler, call both in the same handler:

```python
@key.on("toggle")
async def handle():
    await key.start_busy()
    new_state = await smart_home_api.toggle_light()
    key.set("status_color", "#00ff00" if new_state else "#333333")
    await key.finish_busy()
```

Sometimes you don't need a spinner at all — the task resolves instantly.
Since the application controls the busy state, you simply don't call
`start_busy()` for fast operations.

**Validation rules:**
- For `rotation` and `pulse` types, the `node` must exist in the SVG
- For `custom` type, either `assets/spinner.gif` or `assets/spinner/frame_*.png` files must exist

### Complete Example

```yaml
name: SmartLight
type: Key
version: 1
layout: layout.svg

spinner:
  type: rotation
  node: loading_ring
  frames: 8
  interval_ms: 100

bindings:
  label:
    type: text
    node: label
    default: "Light"
  status_color:
    type: color
    node: indicator
    attribute: fill
    default: "#333333"

events:
  - name: toggle
    source: key_press_release
    max_duration_ms: 300
```

```python
from deux.dui import DuiKey, load_package

spec = load_package("./SmartLight.dui")
key = DuiKey(spec)

@key.on("toggle")
async def handle():
    await key.start_busy()
    # Spinner starts — the key still shows the current
    # label and status_color while the spinner animates in the corner.
    await smart_home_api.toggle_light()
    # Don't call finish_busy() here — wait for the state update callback.

async def on_light_state_changed(new_state):
    """Called by your integration when the light confirms its new state."""
    key.set("status_color", "#00ff00" if new_state else "#333333")
    await key.finish_busy()   # stops spinner, re-renders the key
```

---

## Complete Examples

### Touchscreen Card (Audio Player)

```yaml
name: AudioPlayer
type: TouchStripCard
version: 1
layout: layout.svg

bindings:
  title:
    type: text
    node: title
    default: "No Track"
    max_width: 90
    overflow: ellipsis
  artist:
    type: text
    node: artist
    default: ""
  cover:
    type: image
    node: cover
    fit: cover
    placeholder_node: cover_placeholder
  playing:
    type: toggle
    node_on: icon_pause
    node_off: icon_play
    default: false
  progress:
    type: range
    node: progress_bar
    default: 0.0
    direction: horizontal

events:
  - name: toggle_play
    source: encoder_press_release
    max_duration_ms: 250
  - name: next
    source: encoder_turn
    direction: right
  - name: previous
    source: encoder_turn
    direction: left
  - name: seek_forward
    source: encoder_press_turn
    direction: right
    accumulate: true
    accumulate_delay: 0.15
  - name: seek_backward
    source: encoder_press_turn
    direction: left
    accumulate: true
    accumulate_delay: 0.15

regions:
  card:
    x: 0
    y: 0
    width: 197
    height: 98
    events: [tap, long_press]
```

### Physical Key (Status Indicator)

```yaml
name: StatusKey
type: Key
version: 1
layout: layout.svg

bindings:
  label:
    type: text
    node: label
    default: "Status"
  indicator_color:
    type: color
    node: indicator
    attribute: fill
    default: "#333333"
  icon:
    type: iconify
    node: icon_group
    size: 32
    default: "line-md:check-all"

events:
  - name: activate
    source: key_press_release
    max_duration_ms: 300
  - name: hold
    source: key_hold
    hold_ms: 500
```

---

## Using DUI Packages in Python

### Loading a Package

```python
from deux.dui import load_package, load_all_packages

# Load a single package
spec = load_package("path/to/AudioPlayer.dui")

# Load all packages from a directory
packages = load_all_packages("path/to/packages/")
```

### Touchscreen Card

```python
from deux.dui import DuiCard

card = DuiCard(spec, screen)

# Set binding values
card.set("title", "Bohemian Rhapsody")
card.set("artist", "Queen")
card.set("playing", True)
card.set("progress", 0.42)

# Set multiple at once
card.set_many(title="New Song", artist="Artist", progress=0.0)

# Range helpers
card.set_range("progress", 0.75)
card.adjust_range("progress", 0.01)  # increment by 0.01

# Register event handlers
@card.on("toggle_play")
async def on_toggle():
    ...

@card.on("next")
async def on_next():
    ...

# Render to a PIL Image (panel-sized, sized from the SVG's intrinsic dimensions)
image = card.render()

# Or render directly to encoded device-ready bytes
panel_bytes = card.render_bytes(panel_width=800, panel_height=100)
```

### Physical Key

```python
from deux.dui import DuiKey

key = DuiKey(spec, slot)

key.set("label", "Deploy")
key.set("indicator_color", "#00ff00")

@key.on("activate")
async def on_activate():
    ...

# Render to encoded image bytes. key_size is REQUIRED — pass the
# target key dimensions (width, height) in pixels.
image_bytes = key.render_image(key_size=(120, 120))
```

> **Render API note.** `DuiCard` and `DuiKey` deliberately expose different
> render entry points:
>
> - `DuiCard.render()` returns a PIL `Image`. For encoded bytes, use
>   `DuiCard.render_bytes(panel_width=..., panel_height=...)` or, when
>   composing a touch strip, `DuiCard.render_panel_bytes(...)`.
> - `DuiKey.render_image(key_size, image_format="JPEG")` returns encoded
>   device-ready `bytes` directly; there is no `DuiKey.render()` method.

---

## Validation

Packages are validated on load. Common errors:

- Missing required manifest fields (`name`, `type`, `version`, `layout`)
- Unknown binding type
- Binding references a `node` ID that doesn't exist in the SVG
- `toggle` binding missing `node_on` or `node_off`
- `slider` binding missing `min_pos` or `max_pos`
- Duplicate event names
- `hold_ms` used on a non-hold source
- Invalid region coordinates (negative values)
- Invalid `category` value (must be from the controlled vocabulary)
- Invalid `tags` entries (must be non-empty strings)

All validation errors raise `PackageError` with a descriptive message.

---

## Package Verification Tool

Use the verify tool to check packages before publishing to a repository.

### Basic verification

```bash
python -m deux.tools.verify path/to/MyPackage.dui
```

Checks that the package loads correctly and reports warnings for missing metadata, oversized assets, uppercase tags, and unknown manifest keys.

### Strict mode (for repository submission)

```bash
python -m deux.tools.verify --strict path/to/MyPackage.dui
```

Promotes all warnings to errors. Use this as a gate for repository submissions — packages must have `description` and `author` to pass.

### Build a repository index

```bash
python -m deux.tools.verify --index path/to/packages/
```

Verifies all `.dui` packages in a directory and emits a `repository.json` to stdout containing metadata from every valid package. This JSON index is all a repository needs — no external database required.

### Verification checks

| Check | Severity | Description |
|-------|----------|-------------|
| Package loads | error | All `load_package` validation passes |
| `description` present | warning | Non-empty string |
| `author` present | warning | Non-empty string |
| `category` valid | error | Must be from the controlled vocabulary (if set) |
| Tags are lowercase | warning | Each tag should be lowercase |
| `icon` exists | warning | If declared, file must exist in `assets/` |
| Unknown manifest keys | warning | Catches typos like `desciption` |
| Package size | warning | Total assets + SVG under 2 MB |
| `license` is SPDX | warning | No spaces in the license identifier |
