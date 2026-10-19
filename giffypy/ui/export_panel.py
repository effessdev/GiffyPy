# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import os

from PySide6.QtCore import QUrl, Qt

from ..core.session import reset_session
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QSlider, QVBoxLayout, QWidget

from ..core.constants import FPS_STEPS


class WrappingLabel(QLabel):
    """A QLabel that automatically allows breaking long words/paths by inserting zero-width spaces."""

    def setText(self, text):
        if text:
            text = text.replace("/", "/\u200b").replace("\\",
                                                        "\\\u200b").replace("_", "_\u200b")
        super().setText(text)


def _range_slider(callback, lo, hi, value):
    sl = QSlider(Qt.Horizontal)
    sl.setRange(lo, hi)
    sl.setValue(value)
    sl.valueChanged.connect(callback)
    return sl


def _export_button(text, tip, fn):
    b = QPushButton(text)
    b.setMinimumHeight(40)
    b.setToolTip(tip)
    b.clicked.connect(fn)
    return b


def confirm_reset(window):
    if QMessageBox.question(
        window,
        "Discard and Start Over",
        "Discard the current edit and return to the start screen? This cannot be undone.",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    ) == QMessageBox.Yes:
        reset_session(window)


def build_export_panel(window):
    window.fmt = QComboBox()
    window.fmt.addItems(["WebP", "GIF", "MP4", "WebM", "MOV", "MKV"])
    window.fmt.currentIndexChanged.connect(window.refresh)

    window.fps = _range_slider(window.refresh, 0, len(
        FPS_STEPS) - 1, FPS_STEPS.index(10))
    window.scale = _range_slider(window.refresh, 5, 100, 60)
    window.q = _range_slider(window.refresh, 1, 100, 75)

    window.fpsL, window.scL, window.qL = QLabel(), QLabel(), QLabel()

    window.info = WrappingLabel()
    window.info.setWordWrap(True)

    window.overBtn = _export_button(
        "Overwrite Existing File",
        "Save next to the source video, replacing any existing file (asks to confirm)",
        lambda: window.export("overwrite"),
    )
    window.numBtn = _export_button(
        "Save a Numbered Copy",
        "Save next to the source video as \"name (edited N)\" without replacing anything",
        lambda: window.export("numbered"),
    )
    window.saveAsBtn = _export_button(
        "Save To…",
        "Choose where to save the file",
        lambda: window.export("saveas"),
    )

    window.bar = QProgressBar()
    window.bar.setRange(0, 100)

    window.status = WrappingLabel()
    window.status.setWordWrap(True)

    window.folder = QPushButton("Open Video Source Folder")
    window.folder.setMinimumHeight(40)
    window.folder.clicked.connect(
        lambda: window.path and QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.dirname(window.path)))
    )
    window.discard_btn = QPushButton("Discard and Start Over")
    window.discard_btn.setToolTip(
        "Discard the current edit and return to the start screen")
    window.discard_btn.setMinimumHeight(40)
    window.discard_btn.clicked.connect(lambda: confirm_reset(window))
    window.export_title = QLabel("<b>Export</b>")
    window.controls_rule = QFrame()
    window.controls_rule.setFrameShape(QFrame.HLine)
    window.controls_rule.setFrameShadow(QFrame.Plain)
    window.controls_rule.setStyleSheet(
        "QFrame{color:#8a8f98}")
    window.export_toggle = QPushButton("◀")
    window.export_toggle.setToolTip("Collapse export panel")
    window.export_toggle.setFixedWidth(28)
    window.export_toggle.clicked.connect(window.toggle_export_panel)

    right = QVBoxLayout()
    header = QHBoxLayout()
    header.addWidget(window.export_title)
    header.addStretch()
    header.addWidget(window.export_toggle)
    right.addLayout(header)

    # Layout order: Export controls -> info -> folder -> discard_btn -> status
    right.addWidget(window.fmt)
    right.addWidget(window.fpsL)
    right.addWidget(window.fps)
    right.addWidget(window.scL)
    right.addWidget(window.scale)
    right.addWidget(window.qL)
    right.addWidget(window.q)
    right.addWidget(window.info)
    right.addWidget(window.overBtn)
    right.addWidget(window.numBtn)
    right.addWidget(window.saveAsBtn)
    right.addWidget(window.controls_rule)
    right.addWidget(window.folder)
    right.addWidget(window.discard_btn)
    right.addWidget(window.status)

    right.addStretch()

    window.export_controls = [
        window.fmt,
        window.fpsL,
        window.fps,
        window.scL,
        window.scale,
        window.qL,
        window.q,
        window.overBtn,
        window.numBtn,
        window.saveAsBtn,
        window.info,
        window.folder,
        window.discard_btn,
        window.status,
    ]

    panel = QWidget()
    panel.setLayout(right)
    panel.setFixedWidth(250)
    window.export_panel = panel
    window.export_collapsed = False
    return panel
