# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""The speed slider must drive the live preview, not just the export.

EditorController and PreviewManager talk to the media player through
core/playback.sync_rate, so a clip's speed has to reach the player on every
path that moves the playhead: dragging the slider, starting playback, and
crossing a cut mid-playback. These tests pin that wiring down against a fake
window whose timeline math is the real TimelineModel.
"""

import pytest
from PySide6.QtMultimedia import QMediaPlayer

from giffypy.core.editor import EditorController
from giffypy.core.playback import clip_speed
from giffypy.core.preview import PreviewManager
from giffypy.core.segment import Segment
from giffypy.core.timeline_model import TimelineModel
from giffypy.core.constants import SPEED_MAX, SPEED_MIN


class FakeTimeline:
    """Timeline stand-in with the real TimelineModel's seek/track math."""

    def __init__(self, segs):
        self.model = TimelineModel()
        self.model.segs = segs
        self.goto_calls = []
        self.updates = 0

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

    def update(self):
        self.updates += 1


class FakePlayer:
    def __init__(self):
        self.rate = 1.0
        self.position_ms = 0
        self.playing = True
        self.play_calls = 0
        self.pause_calls = 0

    def playbackRate(self):
        return self.rate

    def setPlaybackRate(self, rate):
        self.rate = rate

    def position(self):
        return self.position_ms

    def setPosition(self, ms):
        self.position_ms = ms

    def playbackState(self):
        states = QMediaPlayer.PlaybackState
        return states.PlayingState if self.playing else states.PausedState

    def play(self):
        self.play_calls += 1
        self.playing = True

    def pause(self):
        self.pause_calls += 1
        self.playing = False


class FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _HiddenItem:
    def __init__(self):
        self.hide_calls = 0

    def hide(self):
        self.hide_calls += 1


class FakeWindow:
    def __init__(self, segs):
        self.tl = FakeTimeline(segs)
        self.player = FakePlayer()
        self.playBtn = FakeLabel()
        self.speedVal = FakeLabel()
        self.pitem = _HiddenItem()
        self.sink = object()  # non-None: on_seek skips its delayed proxy hide
        self.prev_dir = None
        self.H = 0
        self.undo = []
        self.speed_before = None
        self.refresh_calls = 0
        self.preview = PreviewManager(self)

    def playing(self):
        return self.player.playing

    def on_seek(self, i, t):
        self.preview.on_seek(i, t)

    def refresh(self):
        self.refresh_calls += 1


def test_dragging_the_slider_changes_clip_speed_and_player_rate():
    win = FakeWindow([Segment(0.0, 10.0, 1.0)])
    win.tl.head = 4.0

    EditorController(win).on_speed(25)  # slider units are tenths of a speed

    assert win.tl.segs[0].speed == 2.5
    assert win.player.rate == 2.5


def test_speed_change_keeps_the_frame_under_the_playhead():
    win = FakeWindow([Segment(0.0, 10.0, 1.0)])
    win.tl.head = 4.0
    _, t_before = win.tl.src()

    EditorController(win).on_speed(20)  # 2.0x

    _, t_after = win.tl.src()
    assert t_after == pytest.approx(t_before) == pytest.approx(4.0)
    # ...while the playhead itself moves to the faster clip's shorter timeline
    assert win.tl.head == pytest.approx(2.0)
    assert win.tl.total() == pytest.approx(5.0)


def test_resuming_playback_uses_the_selected_clips_speed():
    win = FakeWindow([Segment(0.0, 10.0, 3.0)])
    win.player.playing = False
    win.tl.head = 1.0

    EditorController(win).toggle_play()

    assert win.player.play_calls == 1
    assert win.player.rate == 3.0


def test_starting_playback_seeks_the_player_to_the_stepped_playhead():
    # Reproduce: scrub with the mouse, step with the arrow keys (proxy only),
    # then press space — playback must start under the playhead, not where the
    # mouse left the player.
    win = FakeWindow([Segment(0.0, 10.0, 1.0)])
    win.player.playing = False
    win.player.position_ms = 8000  # stale: last mouse scrub position
    win.tl.head = 3.0              # arrow keys moved the playhead since then

    EditorController(win).toggle_play()

    assert win.player.position_ms == 3000
    assert win.player.play_calls == 1


def test_playback_crossing_a_contiguous_cut_switches_to_the_next_speed():
    win = FakeWindow([Segment(0.0, 2.0, 1.0), Segment(2.0, 6.0, 2.0)])
    win.player.position_ms = 2010  # just past clip 0's end

    EditorController(win).tick()

    assert win.tl.cur == 1
    assert win.player.rate == 2.0
    # 10 ms of source at 2x is 5 ms of playback into clip 1
    assert win.tl.head == pytest.approx(2.0 + 0.005)


def test_playback_at_speed_tracks_the_playhead_in_wall_clock_time():
    win = FakeWindow([Segment(0.0, 10.0, 2.0)])
    win.player.position_ms = 4000  # 4 s of source played at 2x

    EditorController(win).tick()

    assert win.tl.head == pytest.approx(2.0)  # 4 s of source = 2 s of timeline


def test_seeking_positions_the_player_and_applies_that_clips_speed():
    win = FakeWindow([Segment(0.0, 2.0, 1.0), Segment(5.0, 9.0, 2.0)])

    PreviewManager(win).on_seek(1, 5.0)

    assert win.player.rate == 2.0
    assert win.player.position_ms == 5000


def test_clip_speed_is_clamped_to_the_slider_range():
    assert clip_speed(Segment(0.0, 1.0, 8.0)) == SPEED_MAX
    assert clip_speed(Segment(0.0, 1.0, 0.01)) == SPEED_MIN
