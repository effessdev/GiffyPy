# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for Timeline.hit()'s clip/edge/scrub hit-testing, the trickiest
geometry in the editor (edge-grab priority for the selected clip, trim
handle tolerance, ruler-vs-clip-area dispatch)."""

from giffypy.ui.timeline import Timeline


def make_timeline(qtbot, segs, cur=0, width=400, height=110):
    tl = Timeline()
    tl.segs = segs
    tl.dur = sum((e - b) / sp for b, e, sp in segs)
    tl.cur = cur
    tl.resize(width, height)
    tl.fit_view()
    return tl


def test_hit_above_ruler_is_always_scrub(qtbot):
    tl = make_timeline(qtbot, [[0.0, 2.0, 1.0]])
    i, mode = tl.hit(50, 5)  # y < RULER
    assert (i, mode) == (None, 'scrub')


def test_hit_middle_of_clip_is_move(qtbot):
    tl = make_timeline(qtbot, [[0.0, 2.0, 1.0]])
    r = tl.rects()[0]
    cx = (r.left() + r.right()) / 2
    i, mode = tl.hit(cx, r.top() + 5)
    assert (i, mode) == (0, 'move')


def test_hit_left_and_right_edges_of_single_clip(qtbot):
    tl = make_timeline(qtbot, [[0.0, 2.0, 1.0]])
    r = tl.rects()[0]
    y = r.top() + 5

    i, mode = tl.hit(r.left(), y)
    assert (i, mode) == (0, 'l')

    i, mode = tl.hit(r.right(), y)
    assert (i, mode) == (0, 'r')


def test_hit_prioritizes_selected_clip_at_shared_edge(qtbot):
    """Two adjacent clips share an edge; whichever is `cur` should win the
    edge grab there instead of always favoring the earlier clip."""
    segs = [[0.0, 1.0, 1.0], [1.0, 2.0, 1.0]]

    tl = make_timeline(qtbot, segs, cur=0)
    shared_x = tl.rects()[0].right()
    y = tl.rects()[0].top() + 5
    i, mode = tl.hit(shared_x, y)
    assert (i, mode) == (0, 'r')

    tl = make_timeline(qtbot, segs, cur=1)
    shared_x = tl.rects()[1].left()
    i, mode = tl.hit(shared_x, y)
    assert (i, mode) == (1, 'l')


def test_hit_outside_any_clip_falls_back_to_scrub(qtbot):
    tl = make_timeline(qtbot, [[0.0, 1.0, 1.0]])
    r = tl.rects()[0]
    i, mode = tl.hit(r.right() + 200, r.top() + 5)
    assert (i, mode) == (None, 'scrub')
