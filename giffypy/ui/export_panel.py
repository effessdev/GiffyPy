import os

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider, QVBoxLayout, QWidget

from giffypy.constants import FPS_STEPS


def _range_slider(callback, lo, hi, value):
    sl = QSlider(Qt.Horizontal)
    sl.setRange(lo, hi)
    sl.setValue(value)
    sl.valueChanged.connect(callback)
    return sl


def _export_button(text, name, tip, fn):
    b = QPushButton(text)
    b.setObjectName(name)
    b.setMinimumHeight(40)
    b.setToolTip(tip)
    b.clicked.connect(fn)
    return b


def build_export_panel(window):
    window.fmt = QComboBox()
    window.fmt.addItems(["WebP", "GIF", "MP4", "WebM", "MOV", "MKV"])
    window.fmt.currentIndexChanged.connect(window.refresh)

    window.fps = _range_slider(window.refresh, 0, len(FPS_STEPS) - 1, FPS_STEPS.index(10))
    window.scale = _range_slider(window.refresh, 5, 100, 60)
    window.q = _range_slider(window.refresh, 1, 100, 75)
    window.fpsL, window.scL, window.qL, window.info = QLabel(), QLabel(), QLabel(), QLabel()

    window.overBtn = _export_button(
        "Overwrite Existing File",
        "ow",
        "Save next to the source video, replacing any existing file (asks to confirm)",
        lambda: window.export("overwrite"),
    )
    window.numBtn = _export_button(
        "Save a Numbered Copy",
        "go",
        "Save next to the source video as \"name (edited N)\" without replacing anything",
        lambda: window.export("numbered"),
    )
    window.saveAsBtn = _export_button(
        "Save To…",
        "sa",
        "Choose where to save the file",
        lambda: window.export("saveas"),
    )
    window.clipBtn = _export_button(
        "Copy to Clipboard",
        "cp",
        "Export and copy to clipboard (only GIF / WebP support this)",
        window.copy_to_clipboard,
    )

    window.bar = QProgressBar()
    window.bar.setRange(0, 100)
    window.status = QLabel()
    window.status.setWordWrap(True)
    window.folder = QPushButton("Open folder")
    window.folder.clicked.connect(
        lambda: window.path and QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(window.path)))
    )
    window.export_title = QLabel("<b>Export</b>")
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
    window.export_controls = [
        window.fmt,
        window.fpsL,
        window.fps,
        window.scL,
        window.scale,
        window.qL,
        window.q,
        window.info,
        window.overBtn,
        window.numBtn,
        window.saveAsBtn,
        window.clipBtn,
        window.status,
        window.folder,
    ]
    for w in window.export_controls:
        right.addWidget(w)
    right.addStretch()

    panel = QWidget()
    panel.setLayout(right)
    panel.setFixedWidth(250)
    window.export_panel = panel
    window.export_collapsed = False
    return panel
