# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from ..core.constants import SPEED_MAX, SPEED_MIN


def _button(window, text, fn, tip="", checkable=False):
    b = QPushButton(text)
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setFocusPolicy(Qt.NoFocus)
    b.clicked.connect(fn)
    return b


def build_toolbar(window):
    window.playBtn = _button(window, "▶ Play", window.toggle_play, "Space")
    window.cropBtn = _button(
        window, "⛶ Crop", window.toggle_crop, "Show crop rectangle", True)
    window.splitBtn = _button(window, "✂ Split", window.split, "S")
    window.deleteBtn = _button(window, "× Delete clip", window.delete, "Del")
    window.undoBtn = _button(window, "↶ Undo", window.do_undo, "Ctrl+Z")
    window.resetCropBtn = _button(
        window, "Reset crop", lambda: window.crop and window.crop.reset())
    window.zoomOutBtn = _button(
        window, "⌕ −", lambda: window.tl.zoom_by(1 / 1.5), "Zoom out (Ctrl+-)")
    window.zoomInBtn = _button(
        window, "⌕ +", lambda: window.tl.zoom_by(1.5), "Zoom in (Ctrl+=)")
    window.fitBtn = _button(
        window, "Fit", lambda: window.tl.fit_view(), "Fit timeline (Ctrl+0)")
    window.speed = QSlider(Qt.Horizontal)
    window.speed.setRange(int(SPEED_MIN * 10), int(SPEED_MAX * 10))
    window.speed.setValue(10)
    window.speed.setFocusPolicy(Qt.NoFocus)
    window.speed.setFixedWidth(160)
    window.speed.valueChanged.connect(window.on_speed)
    window.speed.sliderPressed.connect(window.on_speed_press)
    window.speed.sliderReleased.connect(window.on_speed_release)
    window.speedVal = QLabel("1.0x")
    window.speedVal.setMinimumWidth(40)

    toolbar = QHBoxLayout()
    for b in (
        window.playBtn,
        window.splitBtn,
        window.deleteBtn,
        window.undoBtn,
        window.cropBtn,
        window.resetCropBtn,
        window.zoomOutBtn,
        window.zoomInBtn,
        window.fitBtn,
    ):
        toolbar.addWidget(b)
    toolbar.addWidget(QLabel("Speed:"))
    toolbar.addWidget(window.speed)
    toolbar.addWidget(window.speedVal)
    toolbar.addStretch()

    hint = QLabel(
        "Drag the top strip to scrub · drag a clip to reorder · drag clip edges to trim · S split · Del delete · "
        "Ctrl+Wheel zoom / two-finger zoom · middle-drag / two-finger drag pan")
    hint.setStyleSheet("color:#888")

    left = QVBoxLayout()
    left.addWidget(window.view, 1)
    left.addLayout(toolbar)
    left.addWidget(window.tl)
    left.addWidget(hint)

    window.main_layout = left
    root = QHBoxLayout()
    root.addLayout(left, 1)
    root.addWidget(window.export_panel)
    container = QWidget()
    container.setLayout(root)
    window.setCentralWidget(container)


def update_toolbar_state(window):
    """Gate toolbar controls to mirror the guards in core/editor.py."""
    has_clips = bool(window.tl.segs)
    window.playBtn.setEnabled(has_clips)
    window.splitBtn.setEnabled(has_clips)
    window.deleteBtn.setEnabled(len(window.tl.segs) > 1)
    window.undoBtn.setEnabled(bool(window.undo))
    has_crop = window.crop is not None
    window.cropBtn.setEnabled(has_crop)
    window.resetCropBtn.setEnabled(has_crop)
    for b in (window.zoomOutBtn, window.zoomInBtn, window.fitBtn):
        b.setEnabled(has_clips)
    window.speed.setEnabled(has_clips)
