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
        # Background for the entire widget
        "QCheckBox{background:#2b2d30;padding:5px;border-radius:4px;}"
        "QGraphicsView{background:#111}"
    )
