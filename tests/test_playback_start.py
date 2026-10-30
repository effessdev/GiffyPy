# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""Starting playback must be instant when the player is already parked on the
playhead.

Seeking is the slow path: the backend re-demuxes and decodes forward from the
previous keyframe, so a seek on every resume froze playback for a moment and
then snapped the playhead forward by the time it took. toggle_play may only
seek when the playhead really moved without the player (arrow-key stepping, or
a freshly loaded source); a plain pause/resume just plays.
"""

import pytest
from PySide6.QtMultimedia import QMediaPlayer

from giffypy.core.constants import FPS_STEPS
from giffypy.core.editor import EditorController
from giffypy.core.preview import PreviewManager
from giffypy.core.segment import Segment
from giffypy.core.timeline_model import TimelineModel


class FakeTimeline:
    """Timeline stand-in with the real TimelineModel's seek/track math."""

    def __init__(self, segs):
        self.model = TimelineModel()
        self.model.segs = segs
        self.goto_calls = []
        self.seek_to = None

    @property
    def segs(self):
        return self.model.segs

    @segs.setter
    def segs(self, value):
        self.model.segs = value

    @property
    def cur(self):
        return self.model.cur

    @cur.setter
    def cur(self, value):
        self.model.cur = value

    @property
    def head(self):
        return self.model.head

    @head.setter
    def head(self, value):
        self.model.head = value

    def total(self):
        return self.model.total()

    def src(self):
        return self.model.src()

    def track(self, i, t):
        self.model.cur = i
        b, e, sp = self.model.segs[i]
        sp = max(0.01, sp)
        self.model.head = self.model.offset(i) + min(max(t - b, 0), e - b) / sp

    def goto(self, i, t):
        self.track(i, t)
        self.goto_calls.append((i, t))
        if self.seek_to is not None:  # Timeline.seek -> window.on_seek
            self.seek_to(i, t)


class FakePlayer:
    def __init__(self):
        self.rate = 1.0
        self.position_ms = 0
        self.playing = False
        self.seeks = []

    def playbackRate(self):
        return self.rate

    def setPlaybackRate(self, rate):
        self.rate = rate

    def position(self):
        return self.position_ms

    def setPosition(self, ms):
        self.position_ms = ms
        self.seeks.append(ms)

    def playbackState(self):
        states = QMediaPlayer.PlaybackState
        return states.PlayingState if self.playing else states.PausedState

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False


class FakeFps:
    """Combo-box stand-in whose current index selects 30 fps."""

    def value(self):
        return FPS_STEPS.index(30)


class _HiddenItem:
    def __init__(self):
        self.hide_calls = 0

    def hide(self):
        self.hide_calls += 1


class FakeWindow:
    def __init__(self, segs):
        self.tl = FakeTimeline(segs)
        self.player = FakePlayer()
        self.preview = PreviewManager(self)
        self.pitem = _HiddenItem()
        self.sink = object()  # non-None: on_seek skips its delayed proxy hide
        self.prev_dir = None
        self.H = 0
        self.fps = FakeFps()
        self.undo = []
        self.speed_before = None
        self.previewed = []
        self.tl.seek_to = self.on_seek

    def playing(self):
        return self.player.playing

    def on_seek(self, i, t):
        self.preview.on_seek(i, t)

    def show_preview(self, t):
        self.previewed.append(t)

    def refresh(self):
        pass


def test_resuming_after_a_pause_plays_without_seeking():
    win = FakeWindow([Segment(0.0, 10.0, 1.0)])
    editor = EditorController(win)
    editor.toggle_play()  # first start: the player is put on the playhead
    assert win.player.seeks == [0]

    win.player.position_ms = 2500  # played on, the playhead followed the player
    win.tl.head = 2.5
    editor.toggle_play()  # pause
    assert win.playing() is False

    editor.toggle_play()  # resume

    assert win.player.seeks == [0]
    assert win.player.position_ms == 2500  # no snap: plays on from the playhead
    assert win.playing() is True


def test_resuming_after_a_scrub_does_not_seek_a_second_time():
    win = FakeWindow([Segment(0.0, 10.0, 1.0)])
    editor = EditorController(win)

    win.tl.goto(0, 4.0)  # dropping the scrub head: the seek lands on the frame
    assert win.player.seeks == [4000]

    editor.toggle_play()

    assert win.player.seeks == [4000]
    assert win.player.position_ms == 4000


def test_frame_stepping_forces_a_seek_before_playing():
    win = FakeWindow([Segment(0.0, 10.0, 1.0)])
    editor = EditorController(win)
    editor.toggle_play()
    editor.toggle_play()  # pause at the start

    editor.step_frame(1)  # proxy-only: the player stays put
    assert win.player.position_ms == 0
    assert win.playing() is False

    editor.toggle_play()

    assert win.player.seeks[-1] == pytest.approx(1000 / 30, abs=1)
    assert win.playing() is True


def test_a_new_source_is_not_assumed_to_sit_on_the_playhead():
    win = FakeWindow([Segment(0.0, 10.0, 1.0)])
    editor = EditorController(win)
    win.tl.goto(0, 6.0)  # player and playhead agree
    win.player.position_ms = 0  # ... but the player was handed a new source

    win.preview.on_source_changed()

    editor.toggle_play()

    assert win.player.seeks[-1] == 6000


def test_playing_from_the_end_still_restarts_at_the_first_clip():
    win = FakeWindow([Segment(0.0, 10.0, 1.0)])
    win.player.position_ms = 10000
    win.tl.head = 10.0

    EditorController(win).toggle_play()

    assert win.player.seeks == [0]
    assert win.player.position_ms == 0
