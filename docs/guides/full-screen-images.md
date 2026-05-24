# Full-Screen Images

DeUX exposes a dedicated path for painting a single image across the entire
back-panel LCD of a Stream Deck. This is the mechanism behind boot splashes,
loading screens, and lock screens.

The runtime entry points live on
[`deux.runtime.deck.Deck`][deux.runtime.deck.Deck], and the underlying
preparation pipeline (input loading, resize/fit, rotation, JPEG encoding) is
implemented in [`deux.runtime.splash`][deux.runtime.splash].

!!! warning "One-shot blit"
    The full-screen image is uploaded via HID command `0x08`
    (`Update Full Screen Image`) and is **one-shot**. Any subsequent per-key
    (`set_key_image`), per-window (`set_partial_window_image`), or per-screen
    render (`set_screen` / `set_theme`) will paint over it. Use this API for
    transient images such as boot splashes — not as a persistent background
    layer. For persistent backgrounds use the per-screen background in
    [`Screen`][deux.ui.screen.Screen] instead.

---

## Device support

The full-screen image path is available on every device family whose PID
exposes a logical LCD size. At time of writing that includes:

| Family | Logical size |
|--------|--------------|
| Stream Deck Classic | 480 × 272 |
| Stream Deck XL | 1024 × 600 |
| Stream Deck Neo | 480 × 320 |
| Stream Deck + | 800 × 480 |
| Stream Deck + XL | 1280 × 800 |

The list of supported PIDs is sourced from `_LCD_SIZES` in
`deux.runtime.hid.device`. On a device with no known LCD size,
[`Deck.show_full_screen_image`][deux.runtime.deck.Deck.show_full_screen_image]
raises [`DeckError`][deux.runtime.deck.DeckError].

Rotation into the device's transmit orientation is applied automatically;
callers always provide the image in **upright** orientation.

---

## `Deck.show_full_screen_image`

```python
async def show_full_screen_image(
    image: Image.Image | str | Path | bytes,
    *,
    fit: Literal["cover", "contain", "stretch"] = "cover",
    background: tuple[int, int, int] = (0, 0, 0),
    jpeg_quality: int = 90,
    min_display_ms: int = 0,
) -> None
```

### Parameters

| Name | Description |
|------|-------------|
| `image` | Source image. Accepts a `PIL.Image.Image`, a file path (`str` or `Path`), or raw `bytes`. `.svg` files and SVG byte streams are rasterised at the device's logical LCD size; other formats are decoded with Pillow. Pre-encoded JPEG bytes already matching the device transmit size and orientation are passed through untouched. |
| `fit` | Resize strategy. `"cover"` (default) scales to fill and crops the overflow; `"contain"` letterboxes with `background`; `"stretch"` distorts to the exact size. |
| `background` | RGB letterbox colour used under `fit="contain"`. |
| `jpeg_quality` | JPEG encoding quality (1–95). |
| `min_display_ms` | Minimum time (ms) the image must remain visible before the *push* phase of the next batched render may begin. The render's CPU work still runs in parallel; only the final device push is delayed. Useful when the first `set_screen` is very fast and would otherwise clobber the splash before the user can perceive it. |

### Companion methods

* [`Deck.show_splash`][deux.runtime.deck.Deck.show_splash] — semantic alias of
  `show_full_screen_image`, intended for boot/startup use.
* [`Deck.clear_full_screen_image`][deux.runtime.deck.Deck.clear_full_screen_image]
  — clear the LCD to a solid colour via the same HID `0x08` path.

---

## Examples

### Boot splash before the first screen

Hold a splash for at least 500 ms so the user can perceive it even when the
first `set_screen` is very fast:

```python
import asyncio
from deux.runtime.discovery import discover

async def main() -> None:
    deck = (await discover())[0]
    async with deck:
        await deck.show_splash("boot.png", min_display_ms=500)
        await deck.set_screen("home")  # push delayed until 500 ms elapsed

asyncio.run(main())
```

### Letterboxed SVG with a coloured background

```python
await deck.show_full_screen_image(
    "logo.svg",
    fit="contain",
    background=(26, 26, 46),
)
```

### Clear the LCD

```python
await deck.clear_full_screen_image()              # black
await deck.clear_full_screen_image((26, 43, 60))  # custom colour
```

---

## Low-level preparation

When you need the JPEG bytes without uploading them — for caching, testing,
or driving the HID layer directly — call
[`prepare_full_screen_jpeg`][deux.runtime.splash.prepare_full_screen_jpeg]
yourself:

```python
from deux.runtime.splash import prepare_full_screen_jpeg
from deux.runtime.hid.protocol import ImageRotation

jpeg = prepare_full_screen_jpeg(
    "splash.png",
    logical_size=(800, 480),
    rotation=ImageRotation.NONE,
    fit="contain",
    background=(0, 0, 0),
)
```

The companion [`prepare_solid_color_jpeg`][deux.runtime.splash.prepare_solid_color_jpeg]
produces a solid-colour image through the same pipeline, which is what
`Deck.clear_full_screen_image` uses internally.

---

## See also

* [CLI Tools — `deux.tools.splash`](cli-tools.md#deuxtoolssplash--back-panel-splash-image)
  for the same functionality from the command line, without writing any
  Python.
