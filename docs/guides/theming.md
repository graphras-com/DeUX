# Theming

DeUX includes a small theme system that drives the CSS palette used to
rasterise DUI SVG layouts. A theme is a primary RGB colour plus a font
family; from those two inputs DeUX derives an 18-entry palette covering
backgrounds, text, borders, icons, and semantic states (success, warning,
error).

All public theming entry points are re-exported from the top-level
`deux` package:

```python
from deux import Theme, get_active_theme, set_active_theme
```

## Built-in default

A baseline theme is applied automatically when `deux.render` is imported,
so DUI packages render correctly out of the box. The default uses
`rgb(39, 87, 179)` with the `Inter` font family.

```python
from deux import get_active_theme

theme = get_active_theme()
print(theme.primary)        # (39, 87, 179)
print(theme.font_family)    # 'Inter'
```

## Building a theme

Themes are immutable; create them via the factory class methods on
[`Theme`][deux.Theme]:

```python
from deux import Theme

# From an explicit primary colour
brand = Theme.from_color(255, 0, 128, font_family="Roboto")

# Or generate a random, readable palette
random_theme = Theme.from_random()

# Or reset to the bundled default
default = Theme.default()
```

Each theme exposes:

- `primary` — the `(r, g, b)` tuple used to derive the palette
- `font_family` — the CSS font-family name applied to every SVG
- `palette` — a `dict[str, str]` mapping CSS class names to hex colours
- `css` — the complete stylesheet string used by the SVG rasteriser

## Activating a theme

[`set_active_theme`][deux.set_active_theme] swaps the system-wide theme
and updates the SVG rasteriser's stylesheet so all subsequent renders
pick up the new palette:

```python
from deux import Theme, set_active_theme

set_active_theme(Theme.from_color(64, 164, 96))

# Later, restore the default
set_active_theme(None)
```

Because rendered key images are cached, you typically call
`set_active_theme` once during startup before any cards or keys are
drawn.

## CSS classes available to DUI layouts

DUI SVG layouts reference the palette through CSS class names. The full
list, in the order they are generated:

| Class | Role |
|-------|------|
| `background-dark` | Card / key background base |
| `background-light` | Raised background tier |
| `border-primary` | Primary borders |
| `border-secondary` | Subtle borders / dividers |
| `text-primary` | Main label text |
| `text-secondary` | Tinted secondary text |
| `text-accent` | Accent text |
| `text-muted` | De-emphasised text |
| `text-selected` | Selected / highlighted text |
| `text-fancy` | Complementary highlight text |
| `success` | Positive state |
| `warning` | Caution state |
| `error` | Error state |
| `icon` | Default icon stroke / fill |
| `icon-active` | Active icon state |
| `icon-inactive` | Inactive icon state |
| `sliders` | Slider track / handle |
| `dynamic` | Dynamic / animated accents |

## See also

- [`deux.Theme`][deux.Theme]
- [`deux.get_active_theme`][deux.get_active_theme]
- [`deux.set_active_theme`][deux.set_active_theme]
