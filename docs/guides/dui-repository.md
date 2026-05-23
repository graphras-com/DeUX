# DUI Repository & Built-in Packages

DeUX ships with a handful of ready-to-use `.dui` packages and a small
registry — the **DUI repository** — that resolves package *names* like
`"IconKey"` to concrete on-disk packages. This lets you write:

```python
from deux import DuiKey, DuiCard

key  = DuiKey("IconKey")           # bundled
card = DuiCard("DashboardCard")    # bundled
```

…without thinking about file paths. This guide explains the bundled
catalogue, how name resolution works, and how to add your own packages
to the search path.

For authoring new packages, see
[Creating DUI Packages](creating-dui-packages.md).

---

## Built-in Packages

The packages bundled with DeUX live under
`src/deux/dui/packages/` and are always available as the lowest-priority
source. They can be used directly by name.

### `IconKey`

A physical key that renders an [Iconify](https://iconify.design/) icon
with a label and a built-in rotation spinner for busy state.

| Field | Value |
|-------|-------|
| Type | `Key` |
| Description | Button with Iconify icon, label and busy spinner |

**Bindings**

| Name | Type | Default | Notes |
|------|------|---------|-------|
| `icon` | `iconify` | `ph:placeholder-bold` | size 55 px |
| `label` | `text` | `"Icon Key"` | max width 110 px |
| `icon_class` | `css_class` | `icon` | CSS class on the icon node |
| `background_class` | `css_class` | `background-dark` | CSS class on the background node |

**Events**

| Name | Source | Notes |
|------|--------|-------|
| `click` | `key_press_release` | `max_duration_ms: 300` |
| `hold` | `key_hold` | `hold_ms: 350` |
| `press` | `key_press` | |
| `release` | `key_release` | |

**Example**

```python
from deux import DuiKey

key = DuiKey("IconKey")
key.set("label", "Shutdown")
key.set("icon", "mdi:power")

@key.on("click")
async def on_click():
    ...
```

### `PictureKey`

A physical key that displays an image with an optional label and a
built-in rotation spinner.

| Field | Value |
|-------|-------|
| Type | `Key` |
| Description | Button with image, optional label and busy spinner |

**Bindings**

| Name | Type | Default | Notes |
|------|------|---------|-------|
| `picture` | `image` | — | |
| `label` | `text` | `"Picture Key"` | max width 110 px, no wrap |
| `background` | `color` | `#1c1c1c` | sets `color` on the background node |
| `foreground` | `color` | `#dedede` | sets `color` on the foreground node |
| `show_label` | `visibility` | `false` | toggles the label overlay |

**Events**: same as `IconKey` (`click`, `hold`, `press`, `release`).

**Example**

```python
from deux import DuiKey
from PIL import Image

key = DuiKey("PictureKey")
key.set("picture", Image.open("cover.png"))
key.set("label", "Now Playing")
key.set("show_label", True)
```

### `DashboardCard`

A touchscreen card that pages through screens with the encoder and
controls deck brightness.

| Field | Value |
|-------|-------|
| Type | `TouchStripCard` |
| Description | Deck brightness control, Screen cycler and displays date, time |

**Bindings**

| Name | Type | Default | Notes |
|------|------|---------|-------|
| `date` | `text` | `""` | max width 190 px, clip overflow |
| `time` | `text` | `""` | max width 190 px, clip overflow |
| `nav` | `list` | `[Main, Livingroom, Settings]` | active index 0, uses `text-selected` / `text-muted` classes |
| `brightness` | `range` | `0.8` | horizontal |

**Events**

| Name | Source | Notes |
|------|--------|-------|
| `brightness_down` | `encoder_turn` | direction `left` |
| `brightness_up` | `encoder_turn` | direction `right` |
| `next_screen` | `encoder_press_release` | `max_duration_ms: 250` |
| `change_theme` | `encoder_hold` | |

**Example**

```python
from deux import DuiCard

card = DuiCard("DashboardCard")
card.set("time", "12:34")
card.set("date", "Mon 23 May")

@card.on("brightness_up")
async def brighter():
    card.adjust_range("brightness", 0.05)
```

---

## How Name Resolution Works

`DuiCard` and `DuiKey` accept three argument forms:

```python
DuiKey("IconKey")            # str  → resolved by the DUI repository
DuiKey(my_spec)              # PackageSpec → used directly
DuiKey(load_package(path))   # PackageSpec from an explicit path
```

When you pass a `str`, the constructor calls
[`resolve_dui()`][deux.resolve_dui], which delegates to the default
[`DuiRepository`][deux.DuiRepository]. Resolution proceeds in **priority
order**:

1. User-registered directories, **most recently added first**.
2. The bundled packages directory (`src/deux/dui/packages/`), always
   last.

The first directory containing `<name>.dui/` wins. Successful lookups
are cached, so repeated `DuiKey("IconKey")` calls return the same
`PackageSpec` object without re-reading the filesystem.

If no directory contains the requested name, a `PackageError` is raised
with the list of searched paths.

---

## Public API

All of the following are top-level exports from `deux`:

| Symbol | Purpose |
|--------|---------|
| `DuiRepository` | The repository class itself. |
| `add_dui_path(path)` | Register a directory as a DUI source. |
| `remove_dui_path(path)` | Unregister a previously added directory. |
| `resolve_dui(name)` | Resolve a name to a `PackageSpec`. |
| `list_dui_packages()` | List all visible package names (sorted). |
| `clear_dui_cache()` | Drop all cached `PackageSpec` objects. |

### Adding a custom directory

```python
import deux

deux.add_dui_path("~/my-dui-packages")

# Packages in that directory now override bundled ones with the same name
key = deux.DuiKey("IconKey")           # custom IconKey wins
card = deux.DuiCard("MyCustomCard")    # newly visible
```

Newly added directories are inserted at **highest priority**, so they
override both previously added directories and the bundled fallback.
Re-adding an existing path simply promotes it to the top.

### Removing a directory

```python
deux.remove_dui_path("~/my-dui-packages")
```

Raises `ValueError` if the path was not previously registered. The
bundled directory cannot be removed.

### Listing what's visible

```python
import deux

print(deux.list_dui_packages())
# ['DashboardCard', 'IconKey', 'PictureKey']
```

Returns names without the `.dui` suffix, sorted alphabetically.
Duplicates across paths are de-duplicated by name.

### Reloading after edits

The repository caches every resolved package in memory. If you edit a
package on disk while your program is running, call
`clear_dui_cache()` so the next lookup re-reads it:

```python
deux.clear_dui_cache()
key = deux.DuiKey("MyPackage")   # re-read from disk
```

For finer control, call `DuiRepository.invalidate(name)` on a
custom repository instance to drop only one entry.

### Resolving without instantiating a control

`resolve_dui()` returns the validated `PackageSpec` directly — useful
for introspection or for sharing a single spec between multiple
controls:

```python
spec = deux.resolve_dui("IconKey")
print(spec.bindings.keys())   # dict_keys(['icon', 'label', ...])

key_a = deux.DuiKey(spec)
key_b = deux.DuiKey(spec)
```

---

## Passing a String, a `PackageSpec`, or a Loaded Package

The three forms are interchangeable in practice — pick the one that
matches where the package lives.

| Form | When to use it |
|------|----------------|
| `DuiKey("IconKey")` | Bundled package, or a name already on the search path. |
| `DuiKey(spec)` | You already have a `PackageSpec` (e.g. from `resolve_dui` or `load_package`). |
| `DuiKey(load_package("/abs/path/Foo.dui"))` | Ad-hoc loading without touching the repository (good for tests). |

```python
from deux import DuiKey, resolve_dui
from deux.dui import load_package

# By name (uses default repository)
k1 = DuiKey("IconKey")

# By spec
spec = resolve_dui("IconKey")
k2 = DuiKey(spec)

# By explicit path (bypasses the repository entirely)
k3 = DuiKey(load_package("/opt/dui/MyKey.dui"))
```

---

## Using a Custom Repository

The module-level helpers (`add_dui_path`, `resolve_dui`, …) operate on a
lazily-created global `DuiRepository`. For isolation — typically in
tests — you can construct your own:

```python
from deux import DuiRepository

repo = DuiRepository(include_bundled=False)
repo.add_path("/tmp/packages")
spec = repo.resolve("MyPackage")
```

The constructor accepts `include_bundled=False` to omit the bundled
fallback entirely, giving you a clean, isolated registry.

> **Note**: `DuiKey(str)` and `DuiCard(str)` always go through the
> module-level default repository. To use a custom repository, resolve
> the spec yourself and pass it: `DuiKey(repo.resolve("MyPackage"))`.

---

## See Also

- [Creating DUI Packages](creating-dui-packages.md) — author your own packages.
- API reference: [`deux.DuiRepository`][deux.DuiRepository],
  [`deux.add_dui_path`][deux.add_dui_path],
  [`deux.resolve_dui`][deux.resolve_dui].
