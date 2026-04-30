# Example: A Complete Stream Deck App

This page walks through [`examples/streamdeck.py`](https://github.com/graphras-com/DeckUI/blob/main/examples/streamdeck.py),
a single-file demo that exercises every major DeckUI feature. It is the
recommended starting point for new users — clone the repo, plug in any
Stream Deck, and run:

```bash
python examples/streamdeck.py
```

No external services are required. All state lives in memory and every
action is logged to the console.

## What it demonstrates

- **Auto-discovery and lifecycle** via `DeckManager`.
- **Loading `.dui` packages** with `load_package` and using `DuiCard` /
  `DuiKey`.
- **Declarative UI bindings** — `set`, `set_many`, `set_range`, and
  `adjust_range` keep domain values normalised for SVG renderers.
- **Refreshing from any handler** — `request_refresh()` works from key
  handlers, encoder handlers, and background tasks alike.
- **A live countdown timer** driven by an `asyncio` task that ticks
  every second.
- **A live dashboard clock** that updates only when the displayed value
  changes.
- **Multi-screen navigation** — a `main` screen and a `settings` screen
  swap atomically via `Deck.set_screen`.
- **All three key event sources** — `press`, `release`, and the
  higher-level `click`. Scene keys flash their colours while held to
  prove that all three fire.

## Layout

The example is structured as a set of single-purpose **controllers**
that each own one widget plus its state. A top-level
`StreamDeckApp` wires them together and hooks into the manager.

```
StreamDeckApp
├── AudioController        ── AudioCard.dui      (touch-strip card 0)
├── LightsController       ── LightCard.dui      (touch-strip card 1)
├── TimerController        ── TimerCard.dui      (touch-strip card 2)
├── DashboardController    ── DashboardCard.dui  (touch-strip card 3)
├── FavoritesController    ── PictureKey.dui     (keys 0..N favourites)
├── SceneController        ── IconKey.dui        (keys after favourites)
└── NavigationController   ── IconKey.dui        (last key, screen switch)
```

Controllers never talk to the deck directly. They mutate their card's
bindings via `set`/`set_many` and call `card.request_refresh()` when the
display needs to update. The deck transparently re-renders dirty regions
on the next refresh tick.

## The lifecycle

The example follows the canonical DeckUI flow:

```python
async def run() -> None:
    app = StreamDeckApp(MEDIA_CATALOG, SCENE_DEFS)
    manager = DeckManager(brightness=60, auto_reconnect=True)

    @manager.on_connect()
    async def _on_connect(deck):
        await app.on_connect(deck)

    @manager.on_disconnect
    async def _on_disconnect(info):
        await app.on_disconnect(info)

    async with manager:
        await manager.wait_closed()
```

`DeckManager` discovers connected devices, calls `on_connect` once a
deck is ready, and re-fires it on reconnects when `auto_reconnect=True`.
On disconnect, the example shuts down its background tasks cleanly.

## Highlights

### Real countdown timer

`TimerController` runs an `asyncio` task that decrements a counter once
per second. When the user toggles, resets, or adjusts the duration,
state is mutated and a refresh requested — the task itself does no UI
work directly.

```python
async def _tick_loop(self) -> None:
    while True:
        await asyncio.sleep(self.TICK_INTERVAL_S)
        if not self.is_running:
            continue
        if self.remaining > 0:
            self.remaining -= 1
            self._sync_card()
            await self._card.request_refresh()
        if self.remaining <= 0 and self.is_running:
            self.is_running = False
            self._sync_card()
            await self._card.request_refresh()
```

The `request_refresh()` call is wired automatically when the screen is
activated — no need to pass the deck handle into the controller.

### Press, release, and click on the same key

Scene keys register all three handlers. The press/release pair invert
the foreground and background colours so the key visually flashes while
held; click logs the scene name:

```python
@key.on_event("press")
async def _press():
    key.set_many(background=FG, foreground=BG)
    await key.request_refresh()

@key.on_event("release")
async def _release():
    key.set_many(background=BG, foreground=FG)
    await key.request_refresh()

@key.on_event("click")
async def _click():
    log.info("Scene activated: %s", label)
```

### Two screens, one set of controllers

`NavigationController` swaps between a busy `main` screen (favourites,
scenes, all four cards) and a focused `settings` screen (just the
dashboard and lights). The same controllers appear on both — DeckUI
re-renders whatever is installed on the active screen.

```python
async def _toggle(self) -> None:
    target = self._primary if self._on_secondary else self._secondary
    self._on_secondary = not self._on_secondary
    self._render_label()
    await self._deck.set_screen(target)
```

## Try it

Once running, here are some interactions to try:

| Action | Effect |
| ------ | ------ |
| Press a favourite key (cover art) | Starts that track; AudioCard updates instantly |
| Press and hold a scene key | Key inverts colours; releases to log the scene |
| Hold the audio encoder | Toggles play/pause |
| Turn the audio encoder | Volume up/down |
| Click the audio encoder | Mute toggle |
| Press + turn the audio encoder | Previous/next track |
| Click the timer encoder | Start or pause the countdown |
| Hold the timer encoder | Reset the timer |
| Turn the timer encoder | Add/remove 30 seconds |
| Press the Settings key | Switch to the settings screen |

## Full source

The complete example, embedded straight from the repository so it stays
in sync with what you'll run locally:

```python title="examples/streamdeck.py"
--8<-- "examples/streamdeck.py"
```

## Related

- [Creating DUI Packages](guides/creating-dui-packages.md) — how to
  build your own `.dui` cards and keys.
- [API Reference](reference/runtime.md) — full library API documentation.
