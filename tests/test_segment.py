# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Segment domain type. These pin down the backward-compat
contract the rest of the refactor leans on: editor.py, timeline.py and
export.py still read/write segments positionally (b, e, sp = seg;
seg[0] = x; for b, e, sp in segs), so Segment must behave like a
[start, end, speed] list everywhere those call sites touch it."""

import copy

import pytest

from giffypy.core.segment import Segment


def test_named_attribute_access():
    seg = Segment(1.0, 2.5, 1.5)
    assert seg.start == 1.0
    assert seg.end == 2.5
    assert seg.speed == 1.5


def test_default_speed_is_one():
    seg = Segment(0.0, 1.0)
    assert seg.speed == 1.0


def test_list_style_indexing_read_and_write():
    seg = Segment(0.0, 1.0, 1.0)
    assert seg[0] == 0.0
    assert seg[1] == 1.0
    assert seg[2] == 1.0

    seg[0] = 0.25
    seg[1] = 0.75
    seg[2] = 2.0
    assert (seg.start, seg.end, seg.speed) == (0.25, 0.75, 2.0)


def test_invalid_index_raises():
    seg = Segment(0.0, 1.0)
    with pytest.raises(IndexError):
        seg[3]
    with pytest.raises(IndexError):
        seg[3] = 1.0


def test_unpacking_like_a_three_item_sequence():
    seg = Segment(0.0, 2.0, 1.0)
    b, e, sp = seg
    assert (b, e, sp) == (0.0, 2.0, 1.0)


def test_len_is_three():
    assert len(Segment(0.0, 1.0)) == 3


def test_equality_against_plain_list_and_tuple():
    seg = Segment(0.0, 1.0, 1.0)
    assert seg == [0.0, 1.0, 1.0]
    assert seg == (0.0, 1.0, 1.0)
    assert seg != [0.0, 1.0, 2.0]


def test_equality_against_another_segment():
    assert Segment(0.0, 1.0, 1.0) == Segment(0.0, 1.0, 1.0)
    assert Segment(0.0, 1.0, 1.0) != Segment(0.0, 1.0, 2.0)


def test_list_of_segments_compares_equal_to_list_of_lists():
    """Mirrors how editor.py call sites and tests compare window.tl.segs
    against literal [[b, e, sp], ...] expectations."""
    segs = [Segment(0.0, 1.0, 1.0), Segment(1.0, 2.0, 1.0)]
    assert segs == [[0.0, 1.0, 1.0], [1.0, 2.0, 1.0]]


def test_deepcopy_preserves_type_and_is_independent():
    seg = Segment(0.0, 1.0, 1.0)
    clone = copy.deepcopy(seg)
    assert isinstance(clone, Segment)
    assert clone == seg
    clone.start = 0.5
    assert seg.start == 0.0  # original untouched


def test_iterating_preserves_order():
    seg = Segment(0.0, 2.0, 1.5)
    assert list(seg) == [0.0, 2.0, 1.5]
