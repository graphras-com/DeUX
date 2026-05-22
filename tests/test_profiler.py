"""Tests for :mod:`deux.render.profiler`."""

from __future__ import annotations

import logging
import time

import pytest

from deux.render.profiler import RenderProfiler, render_profiler


@pytest.fixture(autouse=True)
def _enable_profiler_debug() -> None:
    """Ensure the profiler logger is at DEBUG for most tests."""
    log = logging.getLogger("deux.render.profiler")
    old_level = log.level
    log.setLevel(logging.DEBUG)
    yield  # type: ignore[misc]
    log.setLevel(old_level)


class TestRenderProfiler:
    """Unit tests for the RenderProfiler class."""

    def test_basic_step_recording(self) -> None:
        """Steps are recorded with names and timings."""
        prof = RenderProfiler("test_op")

        with prof.step("step_a"):
            time.sleep(0.001)
        with prof.step("step_b"):
            time.sleep(0.001)

        prof.finish()

        assert len(prof.steps) == 2
        assert prof.steps[0][0] == "step_a"
        assert prof.steps[1][0] == "step_b"
        assert prof.steps[0][1] > 0.0
        assert prof.steps[1][1] > 0.0

    def test_finish_sums_steps(self) -> None:
        """Finish without argument sums step timings."""
        prof = RenderProfiler("test_op")

        with prof.step("a"):
            time.sleep(0.001)

        prof.finish()
        assert prof.total_ms > 0.0

    def test_finish_with_explicit_time(self) -> None:
        """Finish with explicit elapsed time uses that value."""
        prof = RenderProfiler("test_op")
        prof.finish(elapsed_ms=42.5)
        assert prof.total_ms == 42.5

    def test_nested_steps(self) -> None:
        """Child profiler records nested sub-steps."""
        prof = RenderProfiler("outer")

        with prof.step("parent") as child:
            with child.step("nested_a"):
                pass
            with child.step("nested_b"):
                pass

        prof.finish()

        assert len(prof.steps) == 1
        _, _, child_prof = prof.steps[0]
        assert child_prof is not None
        assert len(child_prof.steps) == 2
        assert child_prof.steps[0][0] == "nested_a"
        assert child_prof.steps[1][0] == "nested_b"

    def test_no_child_profiler_when_no_nested_steps(self) -> None:
        """Child profiler is None when the step has no sub-steps."""
        prof = RenderProfiler("test_op")

        with prof.step("simple"):
            pass

        prof.finish()
        _, _, child_prof = prof.steps[0]
        assert child_prof is None

    def test_name_property(self) -> None:
        """Name property returns the profiler name."""
        prof = RenderProfiler("my_operation")
        assert prof.name == "my_operation"

    def test_log_at_debug_level(self, caplog: logging.LogRecord) -> None:
        """Log method outputs at DEBUG level."""
        with caplog.at_level(logging.DEBUG, logger="deux.render.profiler"):
            prof = RenderProfiler("test_log")
            with prof.step("step_one"):
                pass
            prof.finish(elapsed_ms=10.0)
            prof.log()

        assert "test_log" in caplog.text
        assert "step_one" in caplog.text

    def test_log_silent_above_debug(self, caplog: logging.LogRecord) -> None:
        """Log produces no output when logger is above DEBUG."""
        logging.getLogger("deux.render.profiler").setLevel(logging.INFO)
        prof = RenderProfiler("silent_op")
        with prof.step("should_not_appear"):
            pass
        prof.finish(elapsed_ms=5.0)
        prof.log()

        assert "silent_op" not in caplog.text

    def test_inactive_skips_timing(self, _enable_profiler_debug: None) -> None:
        """When logger is above DEBUG, steps are still yielded but not timed."""
        logging.getLogger("deux.render.profiler").setLevel(logging.INFO)
        prof = RenderProfiler("inactive")
        assert not prof.active

        with prof.step("skipped"):
            pass

        # No steps recorded when inactive
        assert len(prof.steps) == 0

    def test_format_lines_tree_structure(self) -> None:
        """Format lines produce tree connectors."""
        prof = RenderProfiler("tree_test")

        with prof.step("first"):
            pass
        with prof.step("last"):
            pass

        prof.finish(elapsed_ms=20.0)

        lines = prof._format_lines()
        assert len(lines) == 3  # header + 2 steps
        assert "\u251c\u2500" in lines[1]  # non-last connector
        assert "\u2514\u2500" in lines[2]  # last connector

    def test_render_profiler_factory(self) -> None:
        """Factory function creates a RenderProfiler instance."""
        prof = render_profiler("factory_test")
        assert isinstance(prof, RenderProfiler)
        assert prof.name == "factory_test"
