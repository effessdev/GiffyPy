# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

from PySide6.QtGui import QPalette, QColor


# Thin, arrowless scrollbars that float over the content instead of sitting in
# a framed groove. Applied globally so the timeline, combo popups and any
# future scroll area share the same look.
SCROLLBAR_QSS = (
    "QScrollBar{background:transparent;border:none}"
    "QScrollBar:vertical{width:12px}"
    "QScrollBar:horizontal{height:12px}"
    "QScrollBar::handle{background:#4a4e57;border-radius:4px}"
    "QScrollBar::handle:hover{background:#5d6270}"
    "QScrollBar::handle:pressed{background:#3d8bfd}"
    "QScrollBar::handle:disabled{background:#33363b}"
    # Inset the handle only at the ends of its travel so it stays flush with
    # the bar's edges instead of leaving a gap along them
    "QScrollBar::handle:vertical{min-height:28px;margin:2px 0}"
    "QScrollBar::handle:horizontal{min-width:28px;margin:0 2px}"
    # Arrows and their line/page buttons are removed entirely
    "QScrollBar::add-line,QScrollBar::sub-line{width:0;height:0;border:none;background:none}"
    "QScrollBar::add-page,QScrollBar::sub-page{background:none}"
    "QScrollBar::up-arrow,QScrollBar::down-arrow,QScrollBar::left-arrow,QScrollBar::right-arrow"
    "{width:0;height:0;background:none}"
)


def apply_theme(window):
    # Set the global highlight/accent color so Qt natively styles checkboxes with #3d8bfd
    palette = window.palette()
    palette.setColor(QPalette.Highlight, QColor("#3d8bfd"))
    window.setPalette(palette)

    window.setStyleSheet(
        "QWidget{background:#25272b;color:#ddd} "
        "QPushButton{padding:6px 10px;background:#3a3d44;border-radius:5px}"
        "QPushButton:hover{background:#4a4e57}"
        "QPushButton:pressed{background:#2f3237}"
        "QPushButton:disabled{background:#2b2d30;color:#555}"
        "QPushButton:checked{background:#3d8bfd}"
        # Background for the entire widget
        "QCheckBox{background:#2b2d30;padding:5px;border-radius:4px;}"
        "QGraphicsView{background:#111}"
        + SCROLLBAR_QSS
    )
