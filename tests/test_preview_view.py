from giffypy.crop import View
from PySide6.QtWidgets import QApplication, QGraphicsScene
from PySide6.QtCore import QPoint, QRectF, Qt
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _MouseEvent:
    def __init__(self, pos, button, buttons):
        self._pos = pos
        self._button = button
        self._buttons = buttons

    def pos(self):
        return self._pos

    def button(self):
        return self._button

    def buttons(self):
        return self._buttons

    def accept(self):
        pass

    def ignore(self):
        pass


class _WheelEvent:
    def __init__(self, delta):
        self._delta = delta

    def angleDelta(self):
        return QPoint(0, self._delta)

    def accept(self):
        pass

    def ignore(self):
        pass


def test_preview_view_has_bounded_navigation_space():
    app = QApplication.instance() or QApplication([])
    scene = QGraphicsScene()
    view = View(scene)
    view.setSceneRect(QRectF(0, 0, 1920, 1080))

    nav = view.bounds()

    assert nav.isValid()
    assert nav.width() < float("inf")
    assert nav.height() < float("inf")
    assert nav.left() <= 0 <= nav.right()
    assert nav.top() <= 0 <= nav.bottom()
    assert nav.right() >= 1920
    assert nav.bottom() >= 1080


def test_preview_view_pan_moves_scene_center():
    app = QApplication.instance() or QApplication([])
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(0, 0, 1920, 1080))
    view = View(scene)
    view.resize(800, 600)
    view.fit_initial()

    # Zoom in past "fit" so the scene exceeds the viewport and there is
    # navigation space to pan into (panning a fully-fitted frame is a no-op).
    for _ in range(10):
        view.wheelEvent(_WheelEvent(120))

    before = view.mapToScene(view.viewport().rect().center())
    press = _MouseEvent(QPoint(400, 300), Qt.MiddleButton, Qt.MiddleButton)
    move = _MouseEvent(QPoint(600, 400), Qt.MiddleButton, Qt.MiddleButton)

    view.mousePressEvent(press)
    view.mouseMoveEvent(move)

    after = view.mapToScene(view.viewport().rect().center())

    assert after != before
    assert abs(after.x() - before.x()) > 0 or abs(after.y() - before.y()) > 0
