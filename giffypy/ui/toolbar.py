# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget


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
    window.speed = QSlider(Qt.Horizontal)
    window.speed.setRange(1, 40)
    window.speed.setValue(10)
    window.speed.setFocusPolicy(Qt.NoFocus)
    window.speed.setFixedWidth(160)
    window.SPEED_NOTE = ("⚠️ Preview plays clips at source speed. Speed changes "
                         "apply to the exported file only.")
    window.speed.setToolTip(window.SPEED_NOTE)
    window.speed.valueChanged.connect(window.on_speed)
    window.speed.sliderPressed.connect(window.on_speed_press)
    window.speed.sliderReleased.connect(window.on_speed_release)
    window.speedVal = QLabel("1.0x")
    window.speedVal.setMinimumWidth(40)

    toolbar = QHBoxLayout()
    for b in (
        window.playBtn,
        _button(window, "✂ Split", window.split, "S"),
        _button(window, "🗑 Delete clip", window.delete, "Del"),
        _button(window, "↶ Undo", window.do_undo, "Ctrl+Z"),
        window.cropBtn,
        _button(window, "Reset crop",
                lambda: window.crop and window.crop.reset()),
        _button(window, "🔍−", lambda: window.tl.zoom_by(
            1 / 1.5), "Zoom out (Ctrl+-)"),
        _button(window, "🔍+", lambda: window.tl.zoom_by(1.5), "Zoom in (Ctrl+=)"),
        _button(window, "Fit", lambda: window.tl.fit_view(),
                "Fit timeline (Ctrl+0)"),
    ):
        toolbar.addWidget(b)
    toolbar.addWidget(QLabel("Speed:"))
    toolbar.addWidget(window.speed)
    toolbar.addWidget(window.speedVal)
    toolbar.addStretch()

    hint = QLabel(
        "Drag the top strip to scrub · drag a clip to reorder · drag clip edges to trim · S split · Del delete · "
        "· Ctrl+Wheel zoom / two-finger zoom · middle-drag / two-finger drag pan")
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
