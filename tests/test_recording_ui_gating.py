# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from giffypy.window import Main


def _window():
    QApplication.instance() or QApplication([])
    return Main()


def test_capture_controls_are_locked_while_recording():
    win = _window()

    win.set_capture_controls_locked(True)
    assert win.open_file_btn.isEnabled() is False
    assert win.capture_cursor_checkbox.isEnabled() is False

    win.set_capture_controls_locked(False)
    assert win.open_file_btn.isEnabled() is True
    assert win.capture_cursor_checkbox.isEnabled() is True


def test_load_is_ignored_while_recording(monkeypatch):
    win = _window()
    win.screen_recorder = SimpleNamespace(is_recording=True)
    loaded = []
    monkeypatch.setattr(win.loader, "load", loaded.append)
    win.status.setText("Recording")

    win.load(r"C:\fake\clip.mp4")

    assert loaded == []
    assert "Stop the screen recording" in win.status.text()
