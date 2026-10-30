# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import os

from PySide6.QtGui import QPalette, QColor


# QCheckBox has no ::content support, so the tick of a checked box is a bundled
# SVG; it lives next to this module and is copied into the bundle by the spec.
CHECK_ICON = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "check.svg"
).replace("\\", "/")


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
        # Every checkbox shares one look: a dark rounded box that turns white
        # with an accent border and tick once checked. Styling ::indicator drops
        # Qt's native glyph, so each state carries its own border and the tick
        # is drawn from CHECK_ICON.
        "QCheckBox{background:transparent;padding:5px;}"
        "QCheckBox::indicator{width:15px;height:15px;border:1px solid #8a8f98;"
        "border-radius:3px;background:#141618;}"
        "QCheckBox::indicator:hover{border:1px solid #5d6270;background:#212429;}"
        "QCheckBox::indicator:checked{width:15px;height:15px;border:1px solid #ddd;"
        "border-radius:3px;background:#141618;image:url(%s);}"
        "QCheckBox::indicator:checked:hover{border:1px solid #fff;background:#212429;}"
        "QCheckBox::indicator:disabled{border:1px solid #33363b;background:#17191c;}"
        "QCheckBox::indicator:checked:disabled{border:1px solid #5d6270;background:#17191c;}"
        % CHECK_ICON
        + "QGraphicsView{background:#111}"
        + SCROLLBAR_QSS
    )
