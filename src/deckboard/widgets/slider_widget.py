"""SliderWidget — backward-compatible alias for :class:`TouchPanel`.

New code should use :class:`~deckboard.widgets.touch_panel.TouchPanel`
directly.  ``SliderWidget`` is kept so existing imports continue to work
without changes.
"""

from __future__ import annotations

from .touch_panel import TouchPanel

# SliderWidget is now simply an alias for the more general TouchPanel.
SliderWidget = TouchPanel

__all__ = ["SliderWidget"]
