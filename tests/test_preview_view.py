from giffypy.crop import View
from giffypy.window import Main
from PySide6.QtWidgets import QApplication, QGraphicsScene
from PySide6.QtCore import QPoint, QRectF, Qt, QProcess, QEvent, QMimeData, QUrl
from PySide6.QtGui import QCloseEvent, QDropEvent
import os
import pytest

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
    def __init__(self, delta, modifiers=Qt.NoModifier, pixel_delta=QPoint(0, 0)):
        self._delta = delta
        self._modifiers = modifiers
        self._pixel_delta = pixel_delta

    def angleDelta(self):
        return QPoint(0, self._delta)

    def modifiers(self):
        return self._modifiers

    def pixelDelta(self):
        return self._pixel_delta

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
        view.wheelEvent(_WheelEvent(120, Qt.ControlModifier))

    before = view.mapToScene(view.viewport().rect().center())
    press = _MouseEvent(QPoint(400, 300), Qt.MiddleButton, Qt.MiddleButton)
    move = _MouseEvent(QPoint(600, 400), Qt.MiddleButton, Qt.MiddleButton)

    view.mousePressEvent(press)
    view.mouseMoveEvent(move)

    after = view.mapToScene(view.viewport().rect().center())

    assert after != before
    assert abs(after.x() - before.x()) > 0 or abs(after.y() - before.y()) > 0


def test_preview_view_pan_disabled_when_no_file_selected():
    app = QApplication.instance() or QApplication([])
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(0, 0, 800, 450))
    view = View(scene)
    view.set_pan_enabled(False)
    view.resize(800, 600)

    before = view.mapToScene(view.viewport().rect().center())
    press = _MouseEvent(QPoint(400, 300), Qt.MiddleButton, Qt.MiddleButton)
    move = _MouseEvent(QPoint(600, 400), Qt.MiddleButton, Qt.MiddleButton)

    view.mousePressEvent(press)
    view.mouseMoveEvent(move)

    after = view.mapToScene(view.viewport().rect().center())

    assert after == before


def test_preview_view_touchpad_scroll_pans_instead_of_zooming():
    app = QApplication.instance() or QApplication([])
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(0, 0, 1920, 1080))
    view = View(scene)
    view.resize(800, 600)
    view.fit_initial()

    for _ in range(10):
        view.wheelEvent(_WheelEvent(120, Qt.ControlModifier))

    before_center = view.mapToScene(view.viewport().rect().center())
    before_scale = view.transform().m11()
    view.wheelEvent(_WheelEvent(30, Qt.NoModifier, QPoint(0, 30)))
    after_center = view.mapToScene(view.viewport().rect().center())

    assert after_center != before_center
    assert view.transform().m11() == before_scale


def test_preview_view_zoom_disabled_when_no_file_selected():
    app = QApplication.instance() or QApplication([])
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(0, 0, 800, 450))
    view = View(scene)
    view.set_pan_enabled(False)
    view.resize(800, 600)

    initial_scale = view.transform().m11()
    view.wheelEvent(_WheelEvent(120))

    assert view.transform().m11() == initial_scale


def test_main_uses_real_widget_placeholder_and_requires_explicit_open(monkeypatch):
    app = QApplication.instance() or QApplication([])
    win = Main()
    opened = {"value": False}

    def fake_open():
        opened["value"] = True

    monkeypatch.setattr(win, "open", fake_open)
    win.show()
    win.setup_placeholder()

    assert hasattr(win, "placeholder")
    assert win.placeholder is not None
    assert not isinstance(win.placeholder, type(win.scene))

    event = QEvent(QEvent.MouseButtonPress)
    result = win.eventFilter(win.view.viewport(), event)

    assert result is False
    assert opened["value"] is False
    assert win.placeholder.isVisible()


def test_main_placeholder_accepts_files_dragged_onto_it(monkeypatch):
    app = QApplication.instance() or QApplication([])
    win = Main()
    win.show()
    win.setup_placeholder()
    loaded = {}

    def fake_load(path):
        loaded["path"] = path

    monkeypatch.setattr(win, "load", fake_load)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(r"C:\\fake\\clip.mp4")])
    event = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)

    win.placeholder.dragEnterEvent(event)
    win.placeholder.dropEvent(event)

    assert os.path.normpath(loaded["path"]) == os.path.normpath(r"C:\fake\clip.mp4")


def test_main_close_event_handles_deleted_preview_process():
    app = QApplication.instance() or QApplication([])
    win = Main()

    class StaleProcess(QProcess):
        def state(self):
            raise RuntimeError("libshiboken: Internal C++ object (PySide6.QtCore.QProcess) already deleted.")

    win.prev_proc = StaleProcess(win)

    try:
        win.closeEvent(QCloseEvent())
    except RuntimeError as exc:
        pytest.fail(f"closeEvent should ignore stale preview process: {exc}")

    assert win.prev_proc is None
