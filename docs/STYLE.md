# Documentation Style Guide

This page records the writing and terminology conventions used across DeUX's
documentation, README, and in-source docstrings. The goal is consistency in
prose so that the same concept always renders the same way — improving
readability, search, and onboarding for both humans and AI assistants.

When in doubt, follow this guide. When updating docs, prefer normalising
inconsistencies to the forms below.

## Terminology

| Term | Form | When to use | Example |
|------|------|-------------|---------|
| `DUI` | Acronym, **always uppercase** | The declarative UI model as a concept | "DeUX uses a DUI to separate layout from logic." |
| `` `.dui` `` | Lowercase, **monospace**, leading dot | The package directory extension on disk | "A `.dui` package contains an SVG layout and a YAML manifest." |
| `` `deux.dui` `` | Lowercase, **monospace**, dotted | The Python module / import path | "Import `load_package` from `deux.dui`." |
| Stream Deck | Two words, title case, **plain prose** | Elgato's product family, in narrative text | "DeUX targets Elgato Stream Deck devices." |
| `` `StreamDeckPlus` `` etc. | PascalCase, **monospace** | Device identifier values (manifest fields, capabilities) | "Set `device: [StreamDeckPlus]` in the manifest." |
| `` `KeySlot` ``, `` `EncoderSlot` ``, `` `TouchStrip` ``, `` `Screen` `` | PascalCase, **monospace** | The class names | "Each `Screen` owns a list of `KeySlot` instances." |
| key slot, encoder slot, touch strip | Lowercase, **plain prose** | The general concept / common noun | "Bindings target individual key slots." |

### Device identifier reference

The canonical PascalCase identifiers, as exposed by `DeviceCapabilities` and
accepted by `.dui` manifest `device:` fields:

| Identifier | Product |
|------------|---------|
| `StreamDeckClassic` | Stream Deck Classic (original, MK.2) |
| `StreamDeckXL` | Stream Deck XL |
| `StreamDeckNeo` | Stream Deck Neo |
| `StreamDeckPlus` | Stream Deck + |
| `StreamDeckPlusXL` | Stream Deck + XL |

In prose, refer to the products with their marketing names (e.g. "Stream Deck
+"); reserve the monospace identifiers for code, tables that describe
configuration values, and manifest examples.

## Formatting

- Class, function, module, and file-extension names always render in
  `monospace` via backticks.
- Marketing/product names stay in plain prose — no backticks, no PascalCase.
- Use sentence case for headings.
- Wrap lines at ~100 characters in Markdown source where practical, matching
  the project's Ruff line-length target.

## Cross-links

When referring to API symbols in MkDocs pages, prefer mkdocstrings autorefs:

```
[`PackageError`][deux.dui.PackageError]
```

over bare backticks, so the reader can navigate directly to the reference.

## Docstrings

All public Python symbols use NumPy-style docstrings. See the example in
[`CONTRIBUTING.md`](https://github.com/graphras-com/DeUX/blob/main/CONTRIBUTING.md#code-style).
The terminology rules above apply equally to docstring prose.
