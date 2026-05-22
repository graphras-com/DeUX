"""Render pipeline profiler for measuring step-by-step timings.

Provides a lightweight, nestable context-manager-based profiler that
records wall-clock timings for each rendering step.  Results are logged
at ``DEBUG`` level using the standard :mod:`logging` module.

The profiler is always available but only logs when the ``deux.render.profiler``
logger is at ``DEBUG`` level, so there is negligible overhead in production.

Examples
--------
::

    from deux.render.profiler import RenderProfiler

    prof = RenderProfiler("render_screen_complete")
    with prof.step("prefetch_icons"):
        await prefetch_icons(icons)
    with prof.step("render_all_keys"):
        await self.render_all_keys()
    prof.log()
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


class RenderProfiler:
    """Collect wall-clock timings for named rendering steps.

    Each profiler instance tracks a single logical operation (e.g.
    ``"render_screen_complete"``) and records sub-step timings via the
    :meth:`step` context manager.  Steps may be nested: a child profiler
    can be attached to record finer-grained breakdowns.

    Parameters
    ----------
    name : str
        Human-readable name for the operation being profiled.
    parent : RenderProfiler or None, optional
        Parent profiler for nested timing trees.  When set, this
        profiler's summary is included in the parent's log output.
    """

    def __init__(self, name: str, *, parent: RenderProfiler | None = None) -> None:
        self._name = name
        self._parent = parent
        self._steps: list[tuple[str, float, RenderProfiler | None]] = []
        self._total_ms: float = 0.0
        self._active = logger.isEnabledFor(logging.DEBUG)

    @property
    def name(self) -> str:
        """The operation name for this profiler."""
        return self._name

    @property
    def active(self) -> bool:
        """Whether profiling is active (DEBUG logging enabled)."""
        return self._active

    @property
    def steps(self) -> list[tuple[str, float, "RenderProfiler | None"]]:
        """Recorded steps as ``(name, elapsed_ms, child_profiler)`` tuples."""
        return list(self._steps)

    @property
    def total_ms(self) -> float:
        """Total elapsed time in milliseconds (set after :meth:`finish`)."""
        return self._total_ms

    @contextmanager
    def step(self, name: str) -> Generator[RenderProfiler, None, None]:
        """Time a named sub-step.

        Yields a child :class:`RenderProfiler` that can be used for
        further nesting.  The child's timings are automatically attached
        to this profiler's step record.

        Parameters
        ----------
        name : str
            Human-readable name for the sub-step.

        Yields
        ------
        RenderProfiler
            A child profiler for recording nested sub-steps.
        """
        child = RenderProfiler(name, parent=self)
        if not self._active:
            yield child
            return
        t0 = time.perf_counter()
        yield child
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        child._total_ms = elapsed_ms
        self._steps.append((name, elapsed_ms, child if child._steps else None))

    def finish(self, elapsed_ms: float | None = None) -> None:
        """Mark the profiler as finished and set the total elapsed time.

        Parameters
        ----------
        elapsed_ms : float or None, optional
            Total elapsed time.  If ``None``, the sum of recorded steps
            is used.
        """
        if elapsed_ms is not None:
            self._total_ms = elapsed_ms
        else:
            self._total_ms = sum(ms for _, ms, _ in self._steps)

    def log(self) -> None:
        """Log the collected timings at DEBUG level.

        Produces a tree-formatted summary, for example::

            render_screen_complete 142.3ms
              prefetch_icons      12.1ms
              render_all_keys     89.4ms
                render_phase      71.2ms
                push_phase        18.2ms
              render_touchscreen  38.7ms
              render_info_screen   2.1ms
        """
        if not self._active:
            return
        lines = self._format_lines(indent=0)
        logger.debug("\n".join(lines))

    def _format_lines(self, indent: int = 0) -> list[str]:
        """Build human-readable timing lines with tree connectors.

        Parameters
        ----------
        indent : int, default=0
            Current indentation level (number of spaces).

        Returns
        -------
        list[str]
            Formatted lines for logging.
        """
        prefix = " " * indent
        lines: list[str] = []

        if indent == 0:
            lines.append(f"{self._name} {self._total_ms:.1f}ms")
        for i, (step_name, elapsed, child) in enumerate(self._steps):
            is_last = i == len(self._steps) - 1
            connector = "\u2514\u2500" if is_last else "\u251c\u2500"
            lines.append(f"{prefix}  {connector} {step_name} {elapsed:.1f}ms")
            if child and child._steps:
                lines.extend(child._format_lines(indent=indent + 4))
        return lines


def render_profiler(name: str) -> RenderProfiler:
    """Create a new :class:`RenderProfiler` instance.

    Convenience factory that mirrors the common usage pattern.

    Parameters
    ----------
    name : str
        Operation name for the profiler.

    Returns
    -------
    RenderProfiler
        A new profiler instance.
    """
    return RenderProfiler(name)
