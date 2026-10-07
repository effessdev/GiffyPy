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
    def resizeEvent(s, e): super().resizeEvent(
        e); s.fitInView(s.sceneRect(), Qt.KeepAspectRatio)
