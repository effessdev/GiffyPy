# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for TimelineModel: pure Python, no QApplication needed. These
pin down the domain math (total/offset/src/reset) independently of the
Timeline widget that wraps it."""

from giffypy.core.timeline_model import TimelineModel


def test_new_model_is_empty():
    m = TimelineModel()
    assert m.segs == []
    assert m.dur == 0.0
    assert m.cur == 0
    assert m.head == 0.0


def test_total_sums_segment_durations_at_speed():
    m = TimelineModel()
    m.segs = [[0.0, 2.0, 1.0], [2.0, 3.0, 2.0]]  # 2.0s + 0.5s
    assert m.total() == 2.5


def test_total_of_empty_segs_is_zero():
    assert TimelineModel().total() == 0.0


def test_offset_is_cumulative_duration_before_index_i():
    m = TimelineModel()
    m.segs = [[0.0, 1.0, 1.0], [1.0, 3.0, 1.0], [3.0, 4.0, 1.0]]
    assert m.offset(0) == 0.0
    assert m.offset(1) == 1.0
    assert m.offset(2) == 3.0
    assert m.offset(3) == 4.0  # sum of all segments


def test_offset_accounts_for_speed():
    m = TimelineModel()
    m.segs = [[0.0, 2.0, 2.0]]  # 2s of source at 2x = 1s of playback
    assert m.offset(1) == 1.0


def test_src_maps_playhead_to_selected_clips_source_time():
    m = TimelineModel()
    m.segs = [[10.0, 12.0, 1.0], [12.0, 14.0, 1.0]]
    m.cur = 1
    m.head = m.offset(1) + 0.5  # half a second into clip 1's playback
    i, t = m.src()
    assert i == 1
    assert t == 12.5


def test_src_accounts_for_speed_when_mapping_back_to_source():
    m = TimelineModel()
    m.segs = [[0.0, 4.0, 2.0]]  # 4s of source at 2x = 2s playback
    m.cur = 0
    m.head = 1.0  # halfway through the 2s playback
    i, t = m.src()
    assert i == 0
    assert t == 2.0  # halfway through the 4s source


def test_reset_clears_all_state():
    m = TimelineModel()
    m.segs = [[0.0, 1.0, 1.0]]
    m.dur = 5.0
    m.cur = 2
    m.head = 3.0

    m.reset()

    assert m.segs == []
    assert m.dur == 0.0
    assert m.cur == 0
    assert m.head == 0.0
