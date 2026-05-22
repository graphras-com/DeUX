"""Thin base classes for service-backed card and key controllers.

A *controller* in DeUX is the small bridge between a backend service
(audio player, smart bulb, timer, etc.) and a :class:`~deux.DuiCard`
or :class:`~deux.DuiKey`.  It loads a ``.dui`` package, wires
service-event subscriptions to bindings (typically via
:meth:`~deux.DuiCard.bind` / :meth:`~deux.DuiKey.bind`), and
forwards DUI events back to service methods.

These base classes are deliberately minimal: they own no state and
provide only two lifecycle hooks that the application can call
uniformly across every controller.  Subclasses construct the card/key
and wire bindings in ``__init__``; they override
:meth:`on_attach`/:meth:`on_detach` if they need a deck reference (for
deck-owned state like brightness or active screen) or background task
management.

Examples
--------
::

    class AudioController(CardController):
        def __init__(self, catalog, packages_dir):
            self.svc = MockAudioService(catalog)
            self.card = DuiCard(load_package(packages_dir / "AudioCard.dui"))
            self.card.bind_range("volume", self.svc.on_volume_changed,
                                 min_val=0, max_val=100)
            self.card.forward("volume_up",
                              lambda steps: self.svc.set_volume(self.svc.volume + steps))

The application then iterates uniformly::

    for c in self._controllers:
        await c.on_attach(deck)
    ...
    for c in self._controllers:
        await c.on_detach()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..dui.card import DuiCard
    from ..dui.key import DuiKey
    from ..runtime.deck import Deck


class CardController:
    """Base class for service-backed touch-strip card controllers.

    Subclasses are expected to:

    1. Load a ``.dui`` package and assign the resulting
       :class:`~deux.DuiCard` to :attr:`card` in ``__init__``.
    2. Wire service-event subscriptions and DUI-event forwards (typically
       via :meth:`~deux.DuiCard.bind`,
       :meth:`~deux.DuiCard.bind_range`,
       :meth:`~deux.DuiCard.bind_many`,
       :meth:`~deux.DuiCard.forward`).
    3. Optionally override :meth:`on_attach` / :meth:`on_detach` for
       deck-linked subscriptions or background task lifecycle.

    The base class itself stores no state and performs no wiring.  It
    exists purely to give every controller a uniform lifecycle the
    application can drive in a loop on connect/disconnect.

    Attributes
    ----------
    card : DuiCard
        The card the controller drives.  Subclasses must assign this.
    """

    card: DuiCard

    async def on_attach(self, deck: Deck) -> None:
        """Hook invoked from the app's ``on_connect`` callback.

        Default implementation is a no-op.  Override to subscribe to
        deck-owned events (e.g. ``deck.on_brightness_changed``), replay
        last-known values to the freshly-connected hardware, or start
        background tasks that depend on a refresh callback being wired
        up.

        Parameters
        ----------
        deck
            The freshly-connected :class:`~deux.Deck` instance.
        """

    async def on_detach(self) -> None:
        """Hook invoked from the app's ``on_disconnect`` callback.

        The default implementation is a no-op.  Override to cancel
        background tasks or perform additional teardown.

        .. note::

           Deck-owned event subscriptions (e.g. ``on_brightness_changed``)
           are cleaned up automatically by :meth:`Deck.stop` via
           :meth:`~deux.DuiCard.detach_events`.  Service-owned bindings
           established in ``__init__`` are deliberately preserved so that
           they survive reconnect cycles without re-wiring.
        """


class KeyController:
    """Base class for service-backed key controllers.

    Mirror of :class:`CardController` for :class:`~deux.DuiKey`.
    Subclasses construct the key and wire bindings in ``__init__``;
    override :meth:`on_attach` / :meth:`on_detach` when deck access
    or background tasks are required.

    Attributes
    ----------
    key : DuiKey
        The key the controller drives.  Subclasses must assign this.
    """

    key: DuiKey

    async def on_attach(self, deck: Deck) -> None:
        """Hook invoked from the app's ``on_connect`` callback.

        Default implementation is a no-op.  See
        :meth:`CardController.on_attach` for guidance.

        Parameters
        ----------
        deck
            The freshly-connected :class:`~deux.Deck` instance.
        """

    async def on_detach(self) -> None:
        """Hook invoked from the app's ``on_disconnect`` callback.

        The default implementation calls :meth:`~deux.DuiKey.detach`
        to unsubscribe all ``AsyncEvent`` handlers.  Override to add
        additional teardown logic, but call ``await super().on_detach()``
        to preserve the unsubscription behaviour.
        """
        if hasattr(self, "key"):
            self.key.detach()
