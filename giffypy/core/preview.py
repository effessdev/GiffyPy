# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import os
import shutil
import tempfile

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtGui import QImage, QPixmap

from .constants import FFMPEG, PREVIEW_FPS, PREVIEW_H
from .playback import sync_rate


class PreviewManager:
    def __init__(self, window):
        self.window = window

    def _clear_prev_proc(self, proc=None):
        if proc is None:
            proc = self.window.prev_proc
        if proc is not None and self.window.prev_proc is proc:
            self.window.prev_proc = None

    def _preview_proc_running(self):
        proc = self.window.prev_proc
        if proc is None:
            return False
        try:
            return proc.state() != QProcess.NotRunning
        except RuntimeError:
            self._clear_prev_proc(proc)
            return False

    def _cleanup_old_dir(self, path):
        """Remove a retired preview-proxy directory and drop it from the
        window's stale-dir tracking list (a safety net for when the app
        closes before the delayed cleanup below gets a chance to fire)."""
        shutil.rmtree(path, ignore_errors=True)
        if path in self.window.stale_prev_dirs:
            self.window.stale_prev_dirs.remove(path)

    def start_preview(self, path):
        """Generate a small JPEG sequence in the background: scrub = O(1) file read, no decoding."""
        proc = self.window.prev_proc
        if proc is not None:
            try:
                if proc.state() != QProcess.NotRunning:
                    proc.kill()
                    proc.waitForFinished(2000)
            except RuntimeError:
                pass
            finally:
                self._clear_prev_proc(proc)
        old, self.window.prev_dir, self.window.prev_cache, self.window.pidx = self.window.prev_dir, None, {}, -1
        self.window.pitem.hide()
        if not FFMPEG:
            return
        self.window.prev_dir = tempfile.mkdtemp(prefix="giffypy_prev_")
        out = os.path.join(self.window.prev_dir, "f%06d.jpg")
        proc = QProcess(self.window)
        self.window.prev_proc = proc
        proc.finished.connect(
            lambda *_, o=proc: (
                self._clear_prev_proc(o),
                o.deleteLater(),
                self.window.status.setText("") if self.window.status.text(
                ) == "Building live preview…" else None,
            ))
        if old:
            self.window.stale_prev_dirs.append(old)
            QTimer.singleShot(1000, lambda: self._cleanup_old_dir(old))
        self.window.status.setText("Building live preview…")
        self.window.prev_fps = min(
            240.0, self.window.src_fps) if self.window.src_fps > 0 else float(PREVIEW_FPS)
        proc.start(FFMPEG, ["-y", "-loglevel", "error", "-i", path, "-an", "-vf",
                            f"scale=-2:min({PREVIEW_H}\\,ih)", "-r", f"{self.window.prev_fps:.9g}",
                            "-q:v", "4", out])

    def show_preview(self, t):
        """Paint the proxy frame nearest source time t over the (slow) video item."""
        if not (self.window.prev_dir and self.window.H) or self.window.playing():
            return
        idx = max(1, int(round(max(0.0, t) * self.window.prev_fps)) + 1)
        if self.window.pidx == idx and self.window.pitem.isVisible():
            return
        pm = self.window.prev_cache.get(idx)
        if pm is None:
            img = QImage(os.path.join(self.window.prev_dir, f"f{idx:06d}.jpg"))
            if img.isNull():
                return
            pm = QPixmap.fromImage(img)
            if len(self.window.prev_cache) > 120:
                self.window.prev_cache.clear()
            self.window.prev_cache[idx] = pm
        self.window.pidx = idx
        self.window.pitem.setPixmap(pm)
        self.window.pitem.setScale(self.window.H / pm.height())
        self.window.pitem.show()

    def on_seek(self, i, t):
        # A seek is the one place every playhead move lands, so it is also where
        # the clip's speed is handed to the player: scrubbing, splitting,
        # deleting, undo and playback crossing a cut all end up here.
        if self.window.tl.segs:
            sync_rate(self.window.player, self.window.tl.segs[i])
        self.window.player.setPosition(int(t * 1000))
        if not self.window.playing():
            self.show_preview(t)
            if self.window.sink is None:
                QTimer.singleShot(300, self.window.pitem.hide)

    def on_real_frame(self, *_):
        """QVideoSink delivered a freshly decoded frame -> retire the proxy."""
        if not self.window.playing():
            self.window.pitem.hide()
