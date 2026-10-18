# GiffyPy - Video editor
# Copyright (C) 2026  Faseeh Zaman F S
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsView

CUR = {'tl': Qt.SizeFDiagCursor, 'br': Qt.SizeFDiagCursor, 'tr': Qt.SizeBDiagCursor, 'bl': Qt.SizeBDiagCursor,
       't': Qt.SizeVerCursor, 'b': Qt.SizeVerCursor, 'l': Qt.SizeHorCursor, 'r': Qt.SizeHorCursor,
       'move': Qt.SizeAllCursor, None: Qt.ArrowCursor}


class CropItem(QGraphicsItem):
    """Image-editor style crop rectangle: drag inside to move, drag handles to resize."""
    def __init__(s, w, h, on_change):
        super().__init__()
        s.W, s.H, s.r, s.mode, s.cb = w, h, QRectF(0, 0, w, h), None, on_change
        s.setAcceptHoverEvents(True)
        s.setZValue(1)

    def boundingRect(s): return QRectF(0, 0, s.W, s.H)

    def hs(s): return 7 / s.scene().views()[0].transform().m11()

    def handles(s):
        r = s.r
        c = r.center()
        return {'tl': r.topLeft(), 't': QPointF(c.x(), r.top()), 'tr': r.topRight(), 'r': QPointF(r.right(), c.y()),
                'br': r.bottomRight(), 'b': QPointF(c.x(), r.bottom()), 'bl': r.bottomLeft(), 'l': QPointF(r.left(), c.y())}

    def paint(s, p, *_):
        path = QPainterPath()
        path.addRect(s.boundingRect())
        path.addRect(s.r)
        p.fillPath(path, QColor(0, 0, 0, 160))
        pen = QPen(QColor("white"), 1)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(s.r)
        pen.setColor(QColor(255, 255, 255, 70))
        p.setPen(pen)
        for i in (1, 2):  # rule-of-thirds guides
            x = s.r.left() + s.r.width() * i / 3
            y = s.r.top() + s.r.height() * i / 3
            p.drawLine(QPointF(x, s.r.top()), QPointF(x, s.r.bottom()))
            p.drawLine(QPointF(s.r.left(), y), QPointF(s.r.right(), y))
        h = s.hs()
        p.setBrush(QColor("white"))
        p.setPen(Qt.NoPen)
        for pt in s.handles().values():
            p.drawRect(QRectF(pt.x() - h / 2, pt.y() - h / 2, h, h))

    def hit(s, pos):
        h = s.hs() * 1.5
        for k, pt in s.handles().items():
            if abs(pos.x() - pt.x()) <= h and abs(pos.y() - pt.y()) <= h:
                return k
        return 'move' if s.r.contains(pos) else None

    def hoverMoveEvent(s, e): s.setCursor(CUR[s.hit(e.pos())])

    def mousePressEvent(s, e): s.mode = s.hit(e.pos()); s.last = e.pos()

    def mouseMoveEvent(s, e):
        if not s.mode:
            return
        r = QRectF(s.r)
        m = s.mode
        p = e.pos()
        if m == 'move':
            d = p - s.last
            s.last = p
            r.translate(d)
            r.moveLeft(max(0, min(s.W - r.width(), r.left())))
            r.moveTop(max(0, min(s.H - r.height(), r.top())))
        else:
            if 'l' in m:
                r.setLeft(max(0, min(p.x(), r.right() - 16)))
            if 'r' in m:
                r.setRight(min(s.W, max(p.x(), r.left() + 16)))
            if 't' in m:
                r.setTop(max(0, min(p.y(), r.bottom() - 16)))
            if 'b' in m:
                r.setBottom(min(s.H, max(p.y(), r.top() + 16)))
        s.r = r
        s.update()
        s.cb()

    def reset(s): s.r = QRectF(0, 0, s.W, s.H); s.update(); s.cb()


class View(QGraphicsView):
    """Preview canvas with bounded pan/zoom navigation.

    The scene is treated as a finite world rather than an unchecked 2D plane:
    panning and zooming are clamped to a finite navigation rectangle so the user
    can explore the frame without drifting off to infinity.
    """

    def __init__(s, scene=None):
        super().__init__(scene)
        s._drag = None
        s._pan_enabled = True
        s.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        s.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        s.setDragMode(QGraphicsView.NoDrag)
        s.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        s.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def set_pan_enabled(s, enabled):
        s._pan_enabled = bool(enabled)
        if not s._pan_enabled:
            s._drag = None
            s.setCursor(Qt.ArrowCursor)

    def is_pan_enabled(s):
        return s._pan_enabled

    def bounds(s):
        rect = s.sceneRect()
        if rect.isNull() or rect.isEmpty():
            return QRectF()
        margin = max(rect.width(), rect.height()) * 0.25
        return rect.adjusted(-margin, -margin, margin, margin)

    def _clamp_view(s):
        nav = s.bounds()
        if nav.isNull():
            return

        center = s.mapToScene(s.viewport().rect().center())
        x = min(max(center.x(), nav.left()), nav.right())
        y = min(max(center.y(), nav.top()), nav.bottom())
        s.centerOn(x, y)

    def fit_initial(s):
        if s.scene() and not s.sceneRect().isEmpty():
            s.fitInView(s.sceneRect(), Qt.KeepAspectRatio)
            s._clamp_view()

    def resizeEvent(s, e):
        super().resizeEvent(e)
        s._clamp_view()

    def wheelEvent(s, ev):
        if not s._pan_enabled:
            ev.ignore()
            return
        if not s.scene() or s.sceneRect().isEmpty():
            return
        delta = ev.angleDelta().y()
        if delta == 0:
            ev.ignore()
            return
        factor = 1.12 if delta > 0 else 1 / 1.12
        scale = s.transform().m11() * factor
        if scale <= 0.05 or scale >= 25.0:
            ev.accept()
            return
        s.scale(factor, factor)
        s._clamp_view()
        ev.accept()

    def mousePressEvent(s, ev):
        if ev.button() == Qt.MiddleButton:
            if not s._pan_enabled:
                ev.ignore()
                return
            s._drag = ev.pos()
            s.setCursor(Qt.ClosedHandCursor)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(s, ev):
        if not s._pan_enabled:
            return
        if s._drag is not None and ev.buttons() & Qt.MiddleButton:
            pos = ev.pos()
            last = s.mapToScene(s._drag)
            current = s.mapToScene(pos)
            delta = current - last
            s._drag = pos
            center = s.mapToScene(s.viewport().rect().center()) - delta
            s.centerOn(center)
            s._clamp_view()
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(s, ev):
        if ev.button() == Qt.MiddleButton:
            if not s._pan_enabled:
                s._drag = None
                s.setCursor(Qt.ArrowCursor)
                return
            s._drag = None
            s.setCursor(Qt.ArrowCursor)
            ev.accept()
            return
        super().mouseReleaseEvent(ev)
