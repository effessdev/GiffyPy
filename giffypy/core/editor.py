# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import copy

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QToolTip

from .constants import FPS_STEPS, MIN


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
        else:
            if self.window.tl.head >= self.window.tl.total() - 0.03:
                self.window.tl.goto(0, self.window.tl.segs[0][0])
            self.window.pitem.hide()
            self.window.player.play()

    def tick(self):
        self.window.playBtn.setText("⏸ Pause" if self.playing() else "▶ Play")
        if not self.window.tl.segs or not self.playing():
            return
        pos = self.window.player.position() / 1000
        i = self.window.tl.cur
        b, e, _sp = self.window.tl.segs[i]
        if pos >= e - 0.01:
            if i + 1 < len(self.window.tl.segs):
                nb = self.window.tl.segs[i + 1][0]
                if abs(nb - e) < 0.03:
                    self.window.tl.track(i + 1, nb)
                else:
                    self.window.tl.goto(i + 1, nb)
            else:
                self.window.player.pause()
                self.window.tl.track(i, e)
        else:
            self.window.tl.track(i, pos)

    def split(self):
        if not self.window.tl.segs:
            return
        i, p = self.window.tl.src()
        b, e, sp = self.window.tl.segs[i]
        if not b + MIN < p < e - MIN:
            return
        self.window.undo.append(copy.deepcopy(self.window.tl.segs))
        self.window.tl.segs[i:i + 1] = [[b, p, sp], [p, e, sp]]
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

    def sync_speed(self):
        if not self.window.tl.segs:
            return
        sp = max(0.1, min(4.0, self.window.tl.segs[self.window.tl.cur][2]))
        self.window.speed.blockSignals(True)
        self.window.speed.setValue(int(round(sp * 10)))
        self.window.speed.blockSignals(False)
        self.window.speedVal.setText(f"{sp:.1f}x")

    def on_speed_press(self):
        self.window.speed_before = copy.deepcopy(self.window.tl.segs)
        QToolTip.showText(
            QCursor.pos(), self.window.SPEED_NOTE, self.window.speed)

    def on_speed(self, v):
        sp = max(0.1, v / 10.0)
        self.window.speedVal.setText(f"{sp:.1f}x")
        if self.window.speed.isSliderDown():
            QToolTip.showText(
                QCursor.pos(), self.window.SPEED_NOTE, self.window.speed)
        if self.window.tl.segs:
            self.window.tl.segs[self.window.tl.cur][2] = sp
            self.window.tl.update()
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
