# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import threading

from PySide6.QtCore import QObject, Signal

from .constants import FFPROBE
from .media import probe


class MediaLoader(QObject):
    finished = Signal(int, str, int, int, float, float)
    failed = Signal(int, str, str)

    def __init__(self, window):
        super().__init__()
        self.window = window

    def load(self, path):
        if not FFPROBE:
            return
        self.window.load_token += 1
        token = self.window.load_token
        self.window.status.setText("Loading file…")
        self.window.bar.setValue(0)
        self.window.busy = True

        def worker():
            try:
                W, H, dur, fps = probe(path)
            except Exception as ex:
                self.failed.emit(token, path, str(ex))
                return
            self.finished.emit(token, path, W, H, dur, fps)

        threading.Thread(target=worker, daemon=True).start()
