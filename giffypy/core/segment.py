# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""The Segment domain type: one clip in the timeline's edit list.

Historically segments were plain [start, end, speed] lists, and editor.py,
timeline.py and export.py all still read and mutate them positionally in
several places (b, e, sp = seg; seg[0] = x; for b, e, sp in segs). Rather
than rewrite every call site at once -- which would touch the timeline's
dense drag/zoom pixel math across several files with no way to verify the
change here -- Segment is a drop-in replacement: it supports the same
list-style indexing, iteration/unpacking, and equality against plain
lists/tuples that existing code already relies on, while also offering
named .start/.end/.speed attributes for new or updated code to prefer over
magic indices 0/1/2.
"""

from dataclasses import dataclass


@dataclass(eq=False)
class Segment:
    """A clip: the source-time span [start, end) played back at `speed`x."""

    start: float
    end: float
    speed: float = 1.0

    def __iter__(self):
        yield self.start
        yield self.end
        yield self.speed

    def __len__(self):
        return 3

    def __getitem__(self, index):
        return (self.start, self.end, self.speed)[index]

    def __setitem__(self, index, value):
        if index == 0:
            self.start = value
        elif index == 1:
            self.end = value
        elif index == 2:
            self.speed = value
        else:
            raise IndexError("Segment index out of range")

    def __eq__(self, other):
        if isinstance(other, Segment):
            return (self.start, self.end, self.speed) == (other.start, other.end, other.speed)
        if isinstance(other, (list, tuple)):
            return (self.start, self.end, self.speed) == tuple(other)
        return NotImplemented
