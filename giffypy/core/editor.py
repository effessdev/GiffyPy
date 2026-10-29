# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import copy

from PySide6.QtMultimedia import QMediaPlayer

from .constants import FPS_STEPS, MIN, SPEED_MIN
from .playback import clip_speed, sync_rate
from .segment import Segment


class EditorController:
    def __init__(self, window):
        self.window = window

    def playing(self):
        return self.window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def step_frame(self, direction):
        """Move the playhead one frame at the export FPS; only repaints the low-res proxy."""
        if not self.window.tl.segs:
            return
        if self.playing():
            self.window.player.pause()
        fps = FPS_STEPS[self.window.fps.value()]
        dt = direction * (1.0 / fps)
        new_head = max(0.0, min(self.window.tl.total(),
                       self.window.tl.head + dt))
        acc = 0.0
        for i, (b, e, sp) in enumerate(self.window.tl.segs):
            sp = max(0.01, sp)
            seg_len = (e - b) / sp
            if new_head <= acc + seg_len or i == len(self.window.tl.segs) - 1:
                t = min(e, b + (new_head - acc) * sp)
                self.window.tl.track(i, t)
                self.window.show_preview(t)
                return
            acc += seg_len

    def commit_step(self):
        """Fetch the full-resolution frame at the current playhead (arrow-key release)."""
        if self.window.tl.segs:
            self.window.on_seek(*self.window.tl.src())

    def toggle_play(self):
        if not self.window.tl.segs:
            return
        if self.playing():
            self.window.player.pause()
            return
        if self.window.tl.head >= self.window.tl.total() - 0.03:
            self.window.tl.goto(0, self.window.tl.segs[0].start)
        else:
            # Arrow-key stepping only repaints the proxy, so the player can
            # still sit where the mouse last left it. Hand the playhead
            # position back to the player before starting, otherwise playback
            # resumes from that stale position. on_seek also applies the
            # current clip's speed.
            self.window.on_seek(*self.window.tl.src())
        self.window.pitem.hide()
        self.window.player.play()

    def tick(self):
        self.window.playBtn.setText("⏸ Pause" if self.playing() else "▶ Play")
        if not self.window.tl.segs or not self.playing():
            return
        pos = self.window.player.position() / 1000
        i = self.window.tl.cur
        b, e, _sp = self.window.tl.segs[i]
        if pos < e - 0.01:
            self.window.tl.track(i, pos)
            return
        if i + 1 < len(self.window.tl.segs):
            nb, ne, _ = self.window.tl.segs[i + 1]
            if abs(nb - e) < 0.03:
                # Contiguous clips: the player already runs on into the next
                # clip's source, so follow its position instead of seeking.
                self.set_rate(i + 1)
                self.window.tl.track(i + 1, min(ne, pos))
            else:
                self.window.tl.goto(i + 1, nb)
        else:
            self.window.player.pause()
            self.window.tl.track(i, e)

    def split(self):
        if not self.window.tl.segs:
            return
        i, p = self.window.tl.src()
        b, e, sp = self.window.tl.segs[i]
        if not b + MIN < p < e - MIN:
            return
        self.window.undo.append(copy.deepcopy(self.window.tl.segs))
        self.window.tl.segs[i:i + 1] = [Segment(b, p, sp), Segment(p, e, sp)]
        self.window.tl.track(i + 1, p)
        self.window.refresh()

    def delete(self):
        if len(self.window.tl.segs) < 2:
            return
        self.window.undo.append(copy.deepcopy(self.window.tl.segs))
        self.window.tl.segs.pop(self.window.tl.cur)
        i = min(self.window.tl.cur, len(self.window.tl.segs) - 1)
        self.window.tl.goto(i, self.window.tl.segs[i][0])
        self.window.refresh()

    def do_undo(self):
        if not self.window.undo:
            return
        self.window.tl.segs = self.window.undo.pop()
        i = min(self.window.tl.cur, len(self.window.tl.segs) - 1)
        self.window.tl.goto(i, self.window.tl.segs[i][0])
        self.window.refresh()

    def on_sel(self, i):
        self.sync_speed()

    def set_rate(self, i):
        """Run the preview player at clip i's speed so playback matches export."""
        if self.window.tl.segs:
            sync_rate(self.window.player, self.window.tl.segs[i])

    def sync_speed(self):
        if not self.window.tl.segs:
            return
        sp = clip_speed(self.window.tl.segs[self.window.tl.cur])
        self.window.speed.blockSignals(True)
        self.window.speed.setValue(int(round(sp * 10)))
        self.window.speed.blockSignals(False)
        self.window.speedVal.setText(f"{sp:.1f}x")

    def on_speed_press(self):
        self.window.speed_before = copy.deepcopy(self.window.tl.segs)

    def on_speed(self, v):
        sp = max(SPEED_MIN, v / 10.0)
        self.window.speedVal.setText(f"{sp:.1f}x")
        if not self.window.tl.segs:
            return
        # Keep the frame under the playhead and re-time the playhead to the new
        # speed, so the preview shows exactly what the export will contain.
        src_t = self.window.tl.src()[1]
        i = self.window.tl.cur
        self.window.tl.segs[i].speed = sp
        self.window.tl.track(i, src_t)
        self.set_rate(i)
        self.window.refresh()

    def on_speed_release(self):
        before = self.window.speed_before
        if before is not None and before != self.window.tl.segs:
            self.window.undo.append(before)
        self.window.speed_before = None
        self.window.refresh()

    def toggle_crop(self):
        if self.window.crop:
            self.window.crop.setVisible(self.window.cropBtn.isChecked())
            self.window.refresh()
