# Creating DUI Packages

A `.dui` package is a self-contained directory that declaratively defines a Stream Deck UI — either a touchscreen card or a physical key — using an SVG layout, a YAML manifest, and optional image assets. No Python rendering code required.

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
| `min_deckui` | `str` | no | Minimum DeckUI version required (e.g. `"0.5.0"`) |
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
min_deckui: "0.5.0"

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
| `encoder_turn` | Encoder rotated; filter with `direction` |
| `encoder_press_turn` | Rotated while pressed; filter with `direction` |
| `encoder_hold` | Held for `hold_ms` |

**Touch sources** (for regions):

| Source | Fires when |
|--------|------------|
| `tap` | Touch tap on a region |
| `long_press` | Long press on a region |

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
  - name: seek_backward
    source: encoder_press_turn
    direction: left

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
from deckui.dui import load_package, load_all_packages

# Load a single package
spec = load_package("path/to/AudioPlayer.dui")

# Load all packages from a directory
packages = load_all_packages("path/to/packages/")
```

### Touchscreen Card

```python
from deckui.dui import DuiCard

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

# Render to image
image = card.render()
```

### Physical Key

```python
from deckui.dui import DuiKey

key = DuiKey(spec, slot)

key.set("label", "Deploy")
key.set("indicator_color", "#00ff00")

@key.on_event("activate")
async def on_activate():
    ...

# Render to encoded image bytes
image_bytes = key.render_image()
```

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
python -m deckui.tools.verify path/to/MyPackage.dui
```

Checks that the package loads correctly and reports warnings for missing metadata, oversized assets, uppercase tags, and unknown manifest keys.

### Strict mode (for repository submission)

```bash
python -m deckui.tools.verify --strict path/to/MyPackage.dui
```

Promotes all warnings to errors. Use this as a gate for repository submissions — packages must have `description` and `author` to pass.

### Build a repository index

```bash
python -m deckui.tools.verify --index path/to/packages/
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
