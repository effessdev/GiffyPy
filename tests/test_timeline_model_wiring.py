# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""Confirms the Timeline widget's segs/dur/cur/head properties are a thin,
transparent pass-through to its embedded TimelineModel -- i.e. that the
refactor genuinely moved the state rather than just adding a parallel copy
of it."""

from giffypy.ui.timeline import Timeline


def test_widget_properties_delegate_to_same_model_instance(qtbot):
    tl = Timeline()

    tl.segs = [[0.0, 2.0, 1.0], [2.0, 4.0, 1.0]]
    tl.dur = 4.0
    tl.cur = 1
    tl.head = 2.5

    # The widget's attributes and the model's attributes are the same data,
    # not independent copies that happen to agree right now.
    assert tl.segs is tl.model.segs
    assert tl.dur == tl.model.dur
    assert tl.cur == tl.model.cur
    assert tl.head == tl.model.head


def test_widget_total_offset_src_match_model(qtbot):
    tl = Timeline()
    tl.segs = [[0.0, 1.0, 1.0], [1.0, 3.0, 2.0]]
    tl.cur = 1
    tl.head = 1.5

    assert tl.total() == tl.model.total()
    assert tl.offset(1) == tl.model.offset(1)
    assert tl.src() == tl.model.src()


def test_reset_clears_model_state_through_the_widget(qtbot):
    tl = Timeline()
    tl.segs = [[0.0, 1.0, 1.0]]
    tl.dur = 1.0
    tl.cur = 0
    tl.head = 0.5

    tl.reset()

    assert tl.segs == []
    assert tl.model.segs == []
    assert tl.dur == 0.0
    assert tl.cur == 0
    assert tl.head == 0.0
