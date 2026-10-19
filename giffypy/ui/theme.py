# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

from PySide6.QtGui import QPalette, QColor


def apply_theme(window):
    # Set the global highlight/accent color so Qt natively styles checkboxes with #3d8bfd
    palette = window.palette()
    palette.setColor(QPalette.Highlight, QColor("#3d8bfd"))
    window.setPalette(palette)

    window.setStyleSheet(
        "QWidget{background:#25272b;color:#ddd} "
        "QPushButton{padding:6px 10px;background:#3a3d44;border-radius:5px}"
        "QPushButton:disabled{background:#2b2d30;color:#555}"
        "QPushButton:checked{background:#3d8bfd}"
        "#ow,#go,#sa,#cp{color:white;font-weight:bold;font-size:13px}"
        "#ow{background:#d9822b} #go{background:#2ea043} #sa{background:#3d8bfd} #cp{background:#8957e5}"
        "#ow:disabled,#go:disabled,#sa:disabled,#cp:disabled{background:#2b2d30;color:#555}"
        # Background for the entire widget
        "QCheckBox{background:#2b2d30;padding:5px;border-radius:4px;}"
        "QGraphicsView{background:#111}"
    )
