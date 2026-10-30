import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QScrollBar, QComboBox

from giffypy.ui.theme import apply_theme

app = QApplication([])
w = QMainWindow()
apply_theme(w)
sb = QScrollBar(Qt.Horizontal, w)
sb.setRange(0, 100)
sb.setPageStep(20)
sb.setValue(0)
sb.resize(300, sb.sizeHint().height())
w.resize(340, 200)
w.show()

img = sb.grab().toImage()
print("bar size:", sb.width(), sb.height())
row = img.height() // 2
colors = [img.pixelColor(x, row).name() for x in (1, 4, 10, 20, 200, 295, 298)]
print("row colors L->R:", colors)

v = QScrollBar(Qt.Vertical, w)
print("vertical width:", v.sizeHint().width())
