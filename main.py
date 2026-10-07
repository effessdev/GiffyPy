#!/usr/bin/env python3
import sys
import os
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from giffypy.window import Main


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    w = Main()
    w.showMaximized()
    if len(sys.argv) > 1:
        w.load(sys.argv[1])
    sys.exit(app.exec())
