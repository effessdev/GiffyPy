# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""The edit-session state that ui/timeline.py's Timeline widget previously
stored directly as its own instance attributes (segs, dur, cur, head).

Pulling it out into a plain object means the clip list, selection and
playhead exist independently of Qt: they can be constructed, mutated and
asserted on in a test with no QApplication, and EditorController's tests
can eventually exercise a real model instead of a hand-rolled duck-typed
fake. Timeline keeps working exactly as before by exposing `segs`/`dur`/
`cur`/`head` as properties that delegate to an embedded TimelineModel, so
no other file's use of `window.tl.segs` etc. needs to change.
"""


class TimelineModel:
    """Owns the clip list (`segs`), its total duration budget (`dur`),
    which clip is selected (`cur`), and the playhead position in the
    concatenated timeline (`head`)."""

    def __init__(self):
        self.segs = []
        self.dur = 0.0
        self.cur = 0
        self.head = 0.0

    def total(self):
        """Sum of each segment's playback duration (end-start)/speed."""
        return sum((e - b) / sp for b, e, sp in self.segs)

    def offset(self, i):
        """Concatenated-timeline start time of segment i."""
        return sum((e - b) / sp for b, e, sp in self.segs[:i])

    def src(self):
        """(selected clip index, source time) the playhead currently maps to."""
        b, e, sp = self.segs[self.cur]
        sp = max(0.01, sp)
        return self.cur, b + (self.head - self.offset(self.cur)) * sp

    def reset(self):
        self.segs = []
        self.dur = 0.0
        self.cur = 0
        self.head = 0.0
