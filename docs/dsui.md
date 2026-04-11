# DSUI — Declarative Stream Deck UI Packages

DSUI (`.dsui`) packages let you describe Stream Deck+ UIs declaratively
using an SVG layout and a YAML manifest instead of writing imperative
Python rendering code.  A package is a directory with a `.dsui` suffix
containing:

```
MyPackage.dsui/
  manifest.yaml      # Required — package metadata, bindings, events, regions
  layout.svg         # Required — the SVG layout referenced by the manifest
  assets/            # Optional — binary assets (images, icons) inlined at render time
    logo.png
```

Load a package and use it as a card or key:

```python
from deckboard.dsui import load_package, DsuiCard, DsuiKey

spec = load_package("./AudioCard.dsui")
card = DsuiCard(0, spec)
card.set("artist", "Ash Walker")

@card.on("toggle_play_pause")
async def handle():
    ...
```

---

## Package types

The `type` field in the manifest determines what hardware target the
package is designed for.

| `type` value       | Class      | Hardware target                          | Supports regions | Supports touch events |
|--------------------|------------|------------------------------------------|------------------|-----------------------|
| `TouchStripCard`   | `DsuiCard` | Touchscreen panel (197 x 98 px)          | Yes              | Yes                   |
| `Key`              | `DsuiKey`  | Physical key (120 x 120 px)              | No               | No                    |

---

## Manifest reference

A minimal manifest:

```yaml
name: MyCard
type: TouchStripCard
version: 1
layout: layout.svg
```

All top-level fields:

| Field      | Type   | Required | Description                                                  |
|------------|--------|----------|--------------------------------------------------------------|
| `name`     | string | Yes      | Unique package name.                                         |
| `type`     | string | Yes      | `TouchStripCard` or `Key`.                                   |
| `version`  | int    | Yes      | Positive integer.  Reserved for future migration support.    |
| `layout`   | string | Yes      | Filename of the SVG layout (must exist in the package dir).  |
| `bindings` | map    | No       | Named data bindings.  Keys are binding names.                |
| `events`   | list   | No       | Event mappings (physical input to semantic event).           |
| `regions`  | map    | No       | Named touchscreen hit-test regions (`TouchStripCard` only).  |

---

## Bindings

Bindings connect named data values to SVG elements.  At runtime you call
`card.set("artist", "Ash Walker")` and the renderer updates the
corresponding SVG node before rasterising.

Every binding has a `type` and a `node` (the `id` attribute of the
target SVG element).  The `node` must exist in the SVG layout.

### Binding types by package type

| Binding type   | `TouchStripCard` | `Key` |
|----------------|------------------|-------|
| `text`         | Yes              | Yes   |
| `image`        | Yes              | Yes   |
| `visibility`   | Yes              | Yes   |
| `color`        | Yes              | Yes   |
| `range`        | Yes              | Yes   |

All five binding types are available in both package types.

---

### `text` — bind text content to a `<text>` element

Sets the text content of an SVG `<text>` element.

```yaml
bindings:
  artist:
    type: text
    node: artist          # SVG element id
    default: ""           # Default text (optional, defaults to "")
    max_width: 90         # Pixel budget for truncation (optional)
    overflow: ellipsis    # How to handle overflow (optional)
```

| Parameter    | Type   | Required | Default    | Description                                              |
|--------------|--------|----------|------------|----------------------------------------------------------|
| `node`       | string | Yes      | —          | `id` of the target `<text>` SVG element.                 |
| `default`    | string | No       | `""`       | Initial text value.                                      |
| `max_width`  | int    | No       | `null`     | Maximum width in pixels. Text exceeding this is handled by `overflow`. |
| `overflow`   | string | No       | `ellipsis` | `ellipsis` — truncate and append `…`. `clip` — leave text unchanged (the SVG viewBox clips it). |

**Runtime value type:** `str`

---

### `image` — bind a PIL Image to an `<image>` element

Replaces the `href` of an SVG `<image>` element with a base64-encoded
data URI of the provided image.

```yaml
bindings:
  cover:
    type: image
    node: cover                    # SVG element id
    fit: cover                     # Scaling strategy (optional)
    placeholder_node: cover_bg     # Shown when no image is set (optional)
```

| Parameter          | Type   | Required | Default  | Description                                              |
|--------------------|--------|----------|----------|----------------------------------------------------------|
| `node`             | string | Yes      | —        | `id` of the target `<image>` SVG element.                |
| `fit`              | string | No       | `cover`  | `cover` — scale to fill, center-crop. `contain` — scale to fit within bounds, center on transparent canvas. `fill` — force-resize to exact target dimensions. |
| `placeholder_node` | string | No       | `null`   | `id` of an SVG element to show when no image is set and hide when an image is set. Must exist in the SVG. |

**Runtime value type:** `PIL.Image.Image` or `bytes` (raw image data). Set to `None` to clear.

When the value is `None`, the `<image>` element is hidden (`display: none`)
and the placeholder node (if configured) is shown.

---

### `visibility` — toggle element visibility

Toggles the `display` CSS property of an SVG element.

```yaml
bindings:
  spinner:
    type: visibility
    node: spinner_group    # SVG element id
    default: true          # Visible by default (optional)
```

| Parameter | Type   | Required | Default | Description                               |
|-----------|--------|----------|---------|-------------------------------------------|
| `node`    | string | Yes      | —       | `id` of the target SVG element.           |
| `default` | bool   | No       | `true`  | Initial visibility state.                 |

**Runtime value type:** `bool` — `True` shows the element (removes
`display` attribute), `False` hides it (`display="none"`).

---

### `color` — bind a colour to fill or stroke

Sets a colour attribute (`fill` or `stroke`) on an SVG element.

```yaml
bindings:
  ring_color:
    type: color
    node: ring             # SVG element id
    attribute: stroke      # Which attribute to set (optional)
    default: "#444444"     # Default colour (optional)
```

| Parameter   | Type   | Required | Default      | Description                              |
|-------------|--------|----------|--------------|------------------------------------------|
| `node`      | string | Yes      | —            | `id` of the target SVG element.          |
| `attribute` | string | No       | `fill`       | SVG attribute to set: `fill` or `stroke`.|
| `default`   | string | No       | `"#ffffff"`  | Default CSS colour value.                |

**Runtime value type:** `str` — any valid CSS colour (`"#ff0000"`,
`"rgb(255,0,0)"`, `"red"`, etc.).

---

### `range` — scale an element's width or height proportionally

Scales an SVG element's `width` (horizontal) or `height` (vertical)
attribute proportionally to a normalised 0.0–1.0 value.  Ideal for
progress bars, volume sliders, level meters, and similar visual
indicators.

The maximum extent is read from the SVG template at load time.  For
example, if the SVG element has `width="185"`, then setting the value to
`0.5` renders `width="92.5"`.

```yaml
bindings:
  volume:
    type: range
    node: volume_bar       # SVG element id
    default: 0.5           # Default proportion (optional)
    direction: horizontal  # Axis to scale (optional)
```

| Parameter   | Type   | Required | Default        | Description                                                  |
|-------------|--------|----------|----------------|--------------------------------------------------------------|
| `node`      | string | Yes      | —              | `id` of the target SVG element (typically a `<rect>`).       |
| `default`   | float  | No       | `0.0`          | Initial value, must be between 0.0 and 1.0 inclusive.        |
| `direction` | string | No       | `horizontal`   | `horizontal` — scales the `width` attribute. `vertical` — scales the `height` attribute. |

**Runtime value type:** `float` — a value between `0.0` (empty) and
`1.0` (full extent).  Values outside this range are clamped.

**SVG design tips:**

- Use a **frame** rect (stroke only, no fill) at the full size, and a
  **fill** rect (the bound element) inside it.  The frame stays fixed
  while the fill rect scales.
- The element's original `width` (or `height`) in the SVG template is
  the 100% reference.  Design your SVG with the bar at full size.
- Combine with a `color` binding on the same node to change the bar
  colour dynamically (e.g., red when muted).

**Example SVG layout:**

```xml
<rect id="volume_frame" x="4" y="72" width="189" height="15"
      stroke="#dedede" fill="none" stroke-width="2" rx="2" ry="2"/>
<rect id="volume_bar" x="6" y="74" width="185" height="11"
      stroke="none" fill="#dedede" rx="1" ry="1"/>
```

```python
card.set("volume", 0.65)   # 65% filled → width becomes 120.25
card.set("volume", 0.0)    # empty bar → width = 0
card.set("volume", 1.0)    # full bar → width = 185
```

---

## Events

Events map physical hardware inputs to named semantic events.  You
define mappings in the manifest and register async handlers in Python:

```python
@card.on("toggle_play_pause")
async def handle():
    ...

# Or imperatively:
card.bind_event("next", my_handler)
```

For `DsuiKey`, use `on_event` instead of `on`:

```python
@key.on_event("activate")
async def handle():
    ...
```

Each mapping in the `events` list has a `name` (the semantic event name
you register handlers against) and a `source` (the physical input type).

```yaml
events:
  - name: toggle_play_pause
    source: encoder_press_release
    max_duration_ms: 250
```

Event names must be unique within a package.

### Event sources by package type

Not all sources are valid for all package types.  The table below shows
which sources apply to each type and what extra parameters they accept.

#### Key sources (`Key` packages only)

These sources fire from physical key presses on the Stream Deck+.

| Source               | Description                                            | Parameters          |
|----------------------|--------------------------------------------------------|---------------------|
| `key_press`          | Fires immediately when the key is pressed down.        | —                   |
| `key_release`        | Fires when the key is released.                        | —                   |
| `key_press_release`  | Fires on release if the press duration is within the limit. A quick-tap gesture. | `max_duration_ms`   |
| `key_hold`           | Fires after the key has been held for a duration.  Suppresses `key_press_release` and `key_release` for that cycle. | `hold_ms` (required)|

#### Encoder sources (`TouchStripCard` packages only)

These sources fire from the rotary encoders beneath the touchscreen.

| Source                  | Description                                             | Parameters             |
|-------------------------|---------------------------------------------------------|------------------------|
| `encoder_press`         | Fires immediately when the encoder is pressed down.     | —                      |
| `encoder_release`       | Fires when the encoder is released.                     | —                      |
| `encoder_press_release` | Fires on release if the press duration is within the limit. A quick-tap gesture. | `max_duration_ms`      |
| `encoder_turn`          | Fires when the encoder is rotated.                      | `direction` (optional) |
| `encoder_press_turn`    | Fires when the encoder is rotated while held down.      | `direction` (optional) |
| `encoder_hold`          | Fires after the encoder has been held for a duration.  Suppresses `encoder_press_release` and `encoder_release` for that cycle. | `hold_ms` (required)   |

#### Touch sources (`TouchStripCard` packages only)

These sources fire from touch input on the touchscreen.  They are
matched against regions (see below) or fire as top-level events if no
region is defined.

| Source        | Description                                              | Parameters |
|---------------|----------------------------------------------------------|------------|
| `tap`         | Short touch on the touchscreen.                          | —          |
| `long_press`  | Long touch on the touchscreen.                           | —          |

### Event parameters reference

| Parameter        | Type   | Required                                  | Description                                           |
|------------------|--------|-------------------------------------------|-------------------------------------------------------|
| `name`           | string | Always                                    | Semantic event name (must be unique in the package).  |
| `source`         | string | Always                                    | Physical input source (see tables above).             |
| `direction`      | string | Optional (only for `encoder_turn`, `encoder_press_turn`) | Direction filter: `left` (counter-clockwise) or `right` (clockwise). Omit to match both directions. |
| `max_duration_ms`| int    | Optional (only for `*_press_release`)     | Maximum press duration in milliseconds.  If the press exceeds this, the event does not fire.  Omit to accept any duration. |
| `hold_ms`        | int    | **Required** for `key_hold`, `encoder_hold`; forbidden on other sources | Hold duration in milliseconds.  The event fires after the key/encoder has been continuously held for this long.  Must be a positive integer. |

---

### Gesture detection

The event map implements several compound gesture patterns automatically:

**Press-release gesture** (`key_press_release`, `encoder_press_release`):
The event map records the press timestamp.  On release, it checks
whether the elapsed time is within `max_duration_ms`.  If so, the
handler fires.  If not (or if a hold fired first), it falls through to
`key_release` / `encoder_release`.

**Hold gesture** (`key_hold`, `encoder_hold`): On press, an async timer
starts.  If the key/encoder is still held when the timer expires, the
hold handler fires.  On release, the timer is cancelled.  If the hold
already fired, `*_press_release` and `*_release` events are
**suppressed** for that press-release cycle — this prevents a hold from
also triggering a tap.

**Press-turn** (`encoder_press_turn`): Turn events while the encoder is
held down are matched against `encoder_press_turn` mappings first, then
fall through to regular `encoder_turn` mappings.

**Priority order on release:**
1. If a hold already fired → suppress all release events.
2. Check `*_press_release` with duration filter.
3. Fall back to `*_release`.

---

## Regions (`TouchStripCard` only)

Regions define rectangular hit-test areas on the touchscreen.  Touch
events are matched against regions before falling through to top-level
touch event mappings.

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

| Parameter | Type      | Required | Description                                             |
|-----------|-----------|----------|---------------------------------------------------------|
| `x`       | int       | Yes      | Left edge (pixels, from card origin). Non-negative.     |
| `y`       | int       | Yes      | Top edge (pixels, from card origin). Non-negative.      |
| `width`   | int       | Yes      | Width in pixels. Non-negative.                          |
| `height`  | int       | Yes      | Height in pixels. Non-negative.                         |
| `events`  | list[str] | No       | Touch event types this region responds to: `tap`, `long_press`, or both. Defaults to empty (region receives no events). |

When a touch event occurs, the event map iterates regions in order and
checks whether the touch coordinates fall within the region bounds and
whether the region accepts that event type.  The first matching region
wins.  If no region matches, the event falls through to top-level `tap`
/ `long_press` event mappings.

Regions are only valid for `TouchStripCard` packages.  `Key` packages do
not have a touchscreen surface.

---

## Assets

Place binary files (PNG, JPEG, etc.) in an `assets/` subdirectory.  The
SVG renderer inlines them automatically: any `<image>` element whose
`href` starts with `assets/` or matches a bare filename in the assets
directory will have its reference replaced with a base64 data URI before
rasterisation.

```
MyCard.dsui/
  manifest.yaml
  layout.svg
  assets/
    logo.png
```

```xml
<!-- In layout.svg — both forms are resolved -->
<image id="logo" href="assets/logo.png" width="32" height="32"/>
<image id="alt"  href="logo.png" width="32" height="32"/>
```

---

## Complete examples

### `TouchStripCard` — audio player

```yaml
name: AudioCard
type: TouchStripCard
version: 1
layout: layout.svg

bindings:
  artist:
    type: text
    node: artist
    default: ""
    max_width: 90
    overflow: ellipsis

  title:
    type: text
    node: title
    default: ""
    max_width: 90
    overflow: ellipsis

  cover:
    type: image
    node: cover
    fit: cover
    placeholder_node: cover_placeholder

  progress_color:
    type: color
    node: progress_bar
    attribute: fill
    default: "#f2b23a"

  progress:
    type: range
    node: progress_bar
    default: 0.0
    direction: horizontal

events:
  - name: toggle_play_pause
    source: encoder_press_release
    max_duration_ms: 250

  - name: previous
    source: encoder_turn
    direction: left

  - name: next
    source: encoder_turn
    direction: right

regions:
  card:
    x: 0
    y: 0
    width: 197
    height: 98
    events: [tap, long_press]
```

```python
from deckboard.dsui import load_package, DsuiCard

spec = load_package("./AudioCard.dsui")
card = DsuiCard(0, spec)

card.set("artist", "Ash Walker").set("title", "Aquamarine")
card.set("progress", 0.35)  # 35% through the track

@card.on("toggle_play_pause")
async def toggle():
    ...

@card.on("previous")
async def prev():
    ...

@card.on("next")
async def nxt():
    ...
```

### `Key` — power button

```yaml
name: PowerKey
type: Key
version: 1
layout: layout.svg

bindings:
  label:
    type: text
    node: label
    default: "Power"

  ring_color:
    type: color
    node: ring
    attribute: stroke
    default: "#444444"

  indicator_color:
    type: color
    node: indicator
    attribute: fill
    default: "#333333"

events:
  - name: activate
    source: key_press_release
    max_duration_ms: 300

  - name: long_hold
    source: key_hold
    hold_ms: 500
```

```python
from deckboard.dsui import load_package, DsuiKey

spec = load_package("./PowerKey.dsui")
key = DsuiKey(0, spec)

key.set("label", "Shutdown")

@key.on_event("activate")
async def activate():
    ...

@key.on_event("long_hold")
async def force_shutdown():
    ...
```

### `TouchStripCard` — volume slider (range binding)

```yaml
name: VolumeSlider
type: TouchStripCard
version: 1
layout: layout.svg

bindings:
  volume:
    type: range
    node: volume_bar
    default: 0.5
    direction: horizontal

  bar_color:
    type: color
    node: volume_bar
    attribute: fill
    default: "#dedede"

  value_text:
    type: text
    node: value_text
    default: "50%"

events:
  - name: volume_up
    source: encoder_turn
    direction: right

  - name: volume_down
    source: encoder_turn
    direction: left

  - name: mute_toggle
    source: encoder_press_release
    max_duration_ms: 300
```

```python
from deckboard.dsui import load_package, DsuiCard

spec = load_package("./VolumeSlider.dsui")
card = DsuiCard(0, spec)

volume = 0.5
card.set("volume", volume)
card.set("value_text", f"{int(volume * 100)}%")

@card.on("volume_up")
async def up():
    nonlocal volume
    volume = min(1.0, volume + 0.05)
    card.set("volume", volume)
    card.set("value_text", f"{int(volume * 100)}%")

@card.on("mute_toggle")
async def mute():
    card.set("bar_color", "#ff4444")
    card.set("value_text", "MUTED")
```

---

## Loading packages

```python
from deckboard.dsui import load_package, load_all_packages

# Load a single package
spec = load_package("./AudioCard.dsui")

# Load all .dsui packages from a directory
packages = load_all_packages("./packages/")
# Returns: {"AudioCard": PackageSpec, "PowerKey": PackageSpec, ...}
```

`load_package` validates the manifest, checks that all binding nodes
exist in the SVG, verifies event source/parameter rules, and loads
assets.  It raises `PackageError` if anything is invalid.

`load_all_packages` scans a directory for subdirectories with a `.dsui`
suffix and loads each one.  Non-`.dsui` directories are ignored.

---

## API summary

### `DsuiCard` (for `TouchStripCard` packages)

| Method / Property       | Description                                          |
|-------------------------|------------------------------------------------------|
| `DsuiCard(index, spec)` | Create a card for touch-strip zone `index` (0-3).    |
| `.set(name, value)`     | Set a binding value. Returns `self`.                 |
| `.set_many(**kwargs)`   | Set multiple bindings at once. Returns `self`.       |
| `.get(name)`            | Get the current value of a binding.                  |
| `.on(event_name)`       | Decorator to register an async event handler.        |
| `.bind_event(name, fn)` | Imperatively register an async event handler.        |
| `.spec`                 | The `PackageSpec` backing this card.                 |
| `.render()`             | Render to a `PIL.Image.Image` (197 x 98 RGB).       |

### `DsuiKey` (for `Key` packages)

| Method / Property          | Description                                       |
|----------------------------|---------------------------------------------------|
| `DsuiKey(index, spec)`     | Create a key for key index `index` (0-7).         |
| `.set(name, value)`        | Set a binding value. Returns `self`.              |
| `.set_many(**kwargs)`      | Set multiple bindings at once. Returns `self`.    |
| `.get(name)`               | Get the current value of a binding.               |
| `.on_event(event_name)`    | Decorator to register an async event handler.     |
| `.bind_event(name, fn)`    | Imperatively register an async event handler.     |
| `.spec`                    | The `PackageSpec` backing this key.               |
| `.render_image()`          | Render to JPEG bytes (120 x 120).                 |
| `.has_dsui_content`        | Always `True`.                                    |
