# CLI Tools

DeUX ships a small set of command-line utilities under `deux.tools` that are
useful while authoring and validating `.dui` packages or iterating on SVG
designs against real hardware. Each tool is invoked via Python's `-m` flag:

```bash
python -m deux.tools.verify   ...
python -m deux.tools.preview  ...
python -m deux.tools.splash   ...
```

All three tools write user-facing messages to **stderr** so that machine
readable output (for example the repository index emitted by `verify
--index`) goes to stdout and can be piped or redirected unmodified.

---

## `deux.tools.verify` — package validation

Validates one `.dui` package, or every `.dui` package in a directory, against
the loader and the repository submission rules. See also the [Package
Verification Tool](creating-dui-packages.md#package-verification-tool) section
of the package authoring guide.

### Synopsis

```bash
python -m deux.tools.verify [-h] [--strict] [--index] [-v] PATH
```

### Arguments

| Flag | Description |
|------|-------------|
| `PATH` | Path to a `.dui` package directory. With `--index`, the path is treated as a parent directory containing many `.dui` packages. |
| `--strict` | Promote warnings to errors. Use this as the gate for repository submission. |
| `--index` | Verify every `.dui` package under `PATH` and emit a repository index JSON document to **stdout** when all packages pass. |
| `-v`, `--verbose` | Enable debug logging on stderr. Useful when investigating why the loader rejects a package. |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed (no error-level diagnostics). |
| `1` | One or more packages produced error-level diagnostics, or the supplied directory does not exist (`--index`). |

### Verification checks

| Check | Severity | Description |
|-------|----------|-------------|
| Package loads | error | All `load_package` validation passes. |
| `description` present | warning | Non-empty string. Required by `--strict`. |
| `author` present | warning | Non-empty string. Required by `--strict`. |
| `category` valid | error | Must be from the controlled vocabulary (if set). |
| Tags are lowercase | warning | Each tag should be lowercase. |
| `icon` exists | warning | If declared, file must exist in `assets/`. |
| Unknown manifest keys | warning | Catches typos such as `desciption`. |
| Package size | warning | Total assets + SVG under 2 MB. |
| `license` is SPDX | warning | No spaces in the license identifier. |

### Examples

Validate a single package:

```bash
python -m deux.tools.verify ./MyPackage.dui
```

Repository submission gate (warnings become errors):

```bash
python -m deux.tools.verify --strict ./MyPackage.dui
```

Build a `repository.json` for all `.dui` packages in a directory:

```bash
python -m deux.tools.verify --index ./packages/ > repository.json
```

Diagnose a load failure with verbose output:

```bash
python -m deux.tools.verify -v ./MyPackage.dui
```

---

## `deux.tools.preview` — live SVG iteration on a deck

Renders one or more SVG files and pushes the result to the first connected
Stream Deck, optionally watching the source files and re-pushing on every
change. The tool auto-discovers the device and adapts to the hardware's
native key / panel geometry — no sizing flags are required.

Only the slots you specify are updated. Slots you omit are left blank
(filled with `--background`, or black if unspecified). Images are scaled
edge-to-edge to fit each slot while preserving aspect ratio; the tool does
not insert margins, padding, or gaps.

### Synopsis

```bash
python -m deux.tools.preview [-h]
    [--key0 SVG] [--key1 SVG] ... [--key7 SVG]
    [--card0 SVG] [--card1 SVG] ... [--card3 SVG]
    [--touchstrip SVG]
    [-b|--brightness PCT]
    [--background HEX]
    [-w|--watch]
    [--poll-interval SECS]
    [-v|--verbose]
```

### Arguments

| Flag | Description |
|------|-------------|
| `--keyN SVG` | SVG file for key slot `N`. The tool declares enough `--keyN` flags to cover the largest current deck; flags that do not correspond to a real slot on the connected device are silently ignored. |
| `--cardN SVG` | SVG file for touchstrip card `N` (one card per touchscreen panel). **Mutually exclusive with `--touchstrip`.** |
| `--touchstrip SVG` | Single SVG that covers the entire touchstrip edge-to-edge. **Mutually exclusive with `--cardN` flags.** |
| `-b`, `--brightness PCT` | Screen brightness, `0`–`100`. Default: `80`. |
| `--background HEX` | Background fill colour for empty space and the touchstrip. Accepts `#rrggbb` or `rrggbb` (case-insensitive). |
| `-w`, `--watch` | Watch all referenced SVG files and re-render / re-push whenever any of them changes on disk. |
| `--poll-interval SECS` | File poll interval when `--watch` is active. Default: `0.5` seconds. |
| `-v`, `--verbose` | Enable debug logging on stderr. |

The process runs until interrupted with `Ctrl+C`. On exit, the deck is
returned to the Elgato boot logo.

### Examples

Push a couple of key designs and a custom background to the deck:

```bash
python -m deux.tools.preview \
    --key0 play.svg --key1 pause.svg \
    --background "#1a2b3c"
```

Iterate on a touchstrip layout with hot-reload — edit the SVG in your editor
and the deck updates within a poll interval:

```bash
python -m deux.tools.preview \
    --card0 now_playing.svg --card1 queue.svg \
    --watch --poll-interval 0.25
```

Use a single full-width SVG across the entire touchstrip:

```bash
python -m deux.tools.preview --touchstrip dashboard.svg --watch
```

---

## `deux.tools.splash` — back-panel splash image

Uploads a single full-screen image to the back-panel LCD via the
`Update Full Screen Image` HID command, or clears the LCD to a solid colour.
This is the quickest way to test the splash pipeline against real hardware
without writing any Python.

!!! note
    The full-screen image is a **one-shot whole-LCD blit**. Any subsequent
    key or touchstrip update — including those issued by another DeUX
    process — will paint over it. See
    `deux.runtime.deck.Deck.show_full_screen_image` for details.

### Synopsis

```bash
python -m deux.tools.splash [-h]
    (--image PATH | --clear)
    [--fit {cover,contain,stretch}]
    [--background COLOR]
    [--quality N]
    [-v|--verbose]
```

Exactly one of `--image` or `--clear` is required.

### Arguments

| Flag | Description |
|------|-------------|
| `--image PATH` | Path to the image to push. Accepts PNG, JPEG, SVG, or any format Pillow can decode. Mutually exclusive with `--clear`. |
| `--clear` | Clear the LCD to a solid colour (the `--background` value). Mutually exclusive with `--image`. |
| `--fit {cover,contain,stretch}` | Resize strategy for `--image`. `cover` (default) fills the LCD and crops overflow, `contain` letterboxes with `--background`, `stretch` distorts to fit. |
| `--background COLOR` | Letterbox / clear colour. Accepts `#rrggbb` or three comma-separated 0–255 integers (`26,43,60`). Default: black. |
| `--quality N` | JPEG encode quality, `1`–`95`. Default: `90`. |
| `-v`, `--verbose` | Enable debug logging on stderr. |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Image pushed (or LCD cleared) successfully. |
| `1` | Bad arguments, or no Stream Deck device found. |
| `2` | Image preparation failed, the device does not expose a full-screen LCD, or an unexpected error occurred while writing to HID. |

### Examples

Push a PNG to the first connected deck (default `cover` fit):

```bash
python -m deux.tools.splash --image boot.png
```

Letterbox an SVG with a coloured background:

```bash
python -m deux.tools.splash --image logo.svg --fit contain --background "#1a1a2e"
```

Clear the LCD to solid black:

```bash
python -m deux.tools.splash --clear
```

Clear the LCD to a custom colour using `r,g,b` notation:

```bash
python -m deux.tools.splash --clear --background 26,43,60
```
