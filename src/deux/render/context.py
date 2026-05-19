"""Explicit rendering context to replace module-level mutable globals.

A :class:`RenderingContext` bundles theme, stylesheet, backend, and
cache references that were previously kept as module-level singletons.
Passing a context through the rendering pipeline eliminates global
state races when two ``DeckManager`` instances with different themes
operate concurrently in the same process.

The module-level globals are preserved as *defaults* — when no explicit
context is supplied, functions fall back to the existing global state
so that simple single-deck usage remains unchanged.

See Also
--------
GitHub issue #199 — Replace module-level mutable globals with explicit
RenderingContext.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .theme import Theme

logger = logging.getLogger(__name__)


@dataclass
class RenderingContext:
    """Immutable-ish bag of rendering state carried through the pipeline.

    Parameters
    ----------
    theme : Theme or None
        The resolved theme for this render pass.  ``None`` means
        "use the system-wide default".
    stylesheet : str or None
        CSS stylesheet text derived from *theme*.  When set, this
        overrides the module-level ``_active_stylesheet`` in
        :mod:`~deux.render.svg_rasterize` for the duration of the
        render.
    backend_name : str or None
        SVG backend name override.  ``None`` means "use the global
        active backend".

    Examples
    --------
    ::

        from deux.render.context import RenderingContext
        from deux.render.theme import Theme

        theme = Theme.from_color(255, 0, 128)
        ctx = RenderingContext(theme=theme, stylesheet=theme.css)
    """

    theme: Theme | None = None
    stylesheet: str | None = None
    backend_name: str | None = None

    @classmethod
    def from_theme(cls, theme: Theme) -> RenderingContext:
        """Create a context from a :class:`Theme`.

        The stylesheet is derived automatically from *theme.css*.

        Parameters
        ----------
        theme : Theme
            The theme to derive the context from.

        Returns
        -------
        RenderingContext
            A new context with *theme* and its CSS.
        """
        return cls(theme=theme, stylesheet=theme.css)

    def resolve_stylesheet(self) -> str | None:
        """Return the effective stylesheet.

        If an explicit stylesheet was provided it is returned.
        Otherwise, if a theme is set, its CSS is used.  Returns
        ``None`` when neither is available.

        Returns
        -------
        str or None
            The CSS stylesheet text, or ``None``.
        """
        if self.stylesheet is not None:
            return self.stylesheet
        if self.theme is not None:
            return self.theme.css
        return None

    def resolve_backend(self) -> str:
        """Return the effective backend name.

        Falls back to ``"auto"`` when no explicit backend is set.

        Returns
        -------
        str
            Backend name.
        """
        return self.backend_name or "auto"
