# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for EditorController.split/delete/do_undo against a minimal
fake window, isolated from the rest of the Qt widget tree."""

import copy

import pytest

from giffypy.core.editor import EditorController


class FakeTimeline:
    """Stand-in for ui.timeline.Timeline exposing only what EditorController touches."""

    def __init__(self, segs, cur=0):
        self.segs = segs
        self.cur = cur
        self.head = 0.0
        self.goto_calls = []
        self.track_calls = []

    def src(self):
        """Same head -> (clip, source time) mapping as TimelineModel.src."""
        b, e, sp = self.segs[self.cur]
        offset = sum((se - sb) / ss for sb, se, ss in self.segs[:self.cur])
        return self.cur, b + max(0.0, self.head - offset) * max(0.01, sp)

    def goto(self, i, t):
        self.cur = i
        self.goto_calls.append((i, t))

    def track(self, i, t):
        self.cur = i
        self.track_calls.append((i, t))


class FakeWindow:
    def __init__(self, segs):
        self.tl = FakeTimeline(segs)
        self.undo = []
        self.refresh_calls = 0

    def refresh(self):
        self.refresh_calls += 1


@pytest.fixture
def window():
    # Three one-second clips at 1.0x speed.
    return FakeWindow([[0.0, 1.0, 1.0], [1.0, 2.0, 1.0], [2.0, 3.0, 1.0]])


def test_split_divides_current_clip_and_pushes_undo(window):
    window.tl.cur = 0
    window.tl.head = 0.5
    before = copy.deepcopy(window.tl.segs)

    EditorController(window).split()

    assert window.tl.segs == [[0.0, 0.5, 1.0], [0.5, 1.0, 1.0],
                              [1.0, 2.0, 1.0], [2.0, 3.0, 1.0]]
    assert window.undo == [before]
    assert window.refresh_calls == 1


def test_split_ignores_cut_too_close_to_clip_edges(window):
    window.tl.cur = 0
    window.tl.head = 0.01  # inside MIN of the left edge
    before = copy.deepcopy(window.tl.segs)

    EditorController(window).split()

    assert window.tl.segs == before
    assert window.undo == []
    assert window.refresh_calls == 0


def test_delete_removes_current_clip_and_clamps_selection(window):
    window.tl.cur = 2  # last clip selected
    before = copy.deepcopy(window.tl.segs)

    EditorController(window).delete()

    assert window.tl.segs == [[0.0, 1.0, 1.0], [1.0, 2.0, 1.0]]
    assert window.undo == [before]
    # cur was clamped back onto the new last clip
    assert window.tl.goto_calls[-1][0] == 1
    assert window.refresh_calls == 1


def test_delete_refuses_to_remove_last_remaining_clip():
    window = FakeWindow([[0.0, 1.0, 1.0]])

    EditorController(window).delete()

    assert window.tl.segs == [[0.0, 1.0, 1.0]]
    assert window.undo == []
    assert window.refresh_calls == 0


def test_do_undo_restores_previous_state_and_pops_stack(window):
    original = copy.deepcopy(window.tl.segs)
    window.undo.append(original)
    window.tl.segs = [[0.0, 0.5, 1.0], [0.5, 1.0, 1.0],
                      [1.0, 2.0, 1.0], [2.0, 3.0, 1.0]]
    window.tl.cur = 3

    EditorController(window).do_undo()

    assert window.tl.segs == original
    assert window.undo == []
    assert window.refresh_calls == 1


def test_do_undo_on_empty_stack_is_a_no_op():
    window = FakeWindow([[0.0, 1.0, 1.0]])

    EditorController(window).do_undo()

    assert window.refresh_calls == 0
    assert window.tl.goto_calls == []
