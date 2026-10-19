# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import shutil

from PySide6.QtCore import QProcess, QUrl


def reset_session(window):
    if window.prev_proc is not None:
        try:
            if window.prev_proc.state() != QProcess.NotRunning:
                window.prev_proc.kill()
                window.prev_proc.waitForFinished(2000)
        except RuntimeError:
            pass
        finally:
            window._clear_prev_proc(window.prev_proc)

    if window.prev_dir:
        shutil.rmtree(window.prev_dir, ignore_errors=True)
        window.prev_dir = None

    if window.screen_recorder.is_recording:
        window.screen_recorder.stop()

    window.player.pause()
    window.player.setSource(QUrl())
    window.pitem.hide()
    window.vitem.hide()
    window.path = None
    window.W = 0
    window.H = 0
    window.undo = []
    window.proxied = False
    window.speed_before = None
    window.prev_cache = {}
    window.pidx = -1
    window.src_fps = 0.0
    window.busy = False
    window.status.setText("")
    window.bar.setValue(0)

    if window.crop is not None:
        window.scene.removeItem(window.crop)
        window.crop = None

    if hasattr(window, "tl"):
        window.tl.reset()

    window.setWindowTitle("GiffyPy")
    window.setup_placeholder()
    window.placeholder.show()
