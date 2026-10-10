import copy

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollBar

from .constants import MIN


class Timeline(QWidget):
    """Clips laid out in edit order. Top strip = scrub, drag clip = reorder, drag clip edge = trim."""
    seek = Signal(int, float)      # clip index, source time
    # live scrub position (source time), proxy frame only
    preview = Signal(float)
    committed = Signal(object)     # previous state (for undo)
    changed = Signal()
    PAD, EDGE, RULER, SB = 10, 7, 20, 14
    MAXZ = 4000.0  # max zoom (pixels per second)

    def __init__(s):
        super().__init__()
        s.segs, s.dur, s.cur, s.head, s.drag = [], 0.0, 0, 0.0, None
        s.before, s.pan = [], None
        # z = px/sec (locked after fit_view on load); ox = scroll offset (px)
        s.z, s.ox = 100.0, 0.0
        s.setMinimumHeight(110)
        s.setMouseTracking(True)
        lay = QVBoxLayout(s)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()
        s.sb = QScrollBar(Qt.Horizontal)
        s.sb.setFixedHeight(s.SB)
        s.sb.valueChanged.connect(s.on_scrollbar)
        lay.addWidget(s.sb)

    def total(s): return sum(e - b for b, e in s.segs)
    def fit(s): return max(1e-3, (s.width() - 2 * s.PAD) / (s.total() or 1e-9))

    def pps(s):
        return s.z

    def offset(s, i): return sum(e - b for b, e in s.segs[:i])

    def lshift(s):
        """While dragging a clip's left edge, the clip keeps its right edge in place
        and its left edge follows the mouse; it only ripples left on release."""
        if s.drag and s.drag[0] == 'l' and s.drag[1] is not None and s.drag[3]:
            i = s.drag[1]
            return i, (s.segs[i][0] - s.drag[3][0]) * s.pps()
        return None, 0.0

    def rects(s):
        x, out = s.PAD - s.ox, []
        si, sh = s.lshift()
        for i, (b, e) in enumerate(s.segs):
            w = (e - b) * s.pps()
            xs = x + (sh if i == si else 0.0)
            out.append(QRectF(xs, s.RULER, w, s.height() - s.RULER - 8 - s.SB))
            x = xs + w
        return out

    # ---- zoom / scroll
    def max_ox(s): return max(0.0, s.total() * s.pps() + 2 * s.PAD - s.width())

    def sync(s):
        s.ox = max(0.0, min(s.max_ox(), s.ox))
        m = int(s.max_ox())
        s.sb.blockSignals(True)
        s.sb.setRange(0, m)
        s.sb.setPageStep(max(1, s.width() - 2 * s.PAD))
        s.sb.setValue(int(s.ox))
        s.sb.setEnabled(m > 0)
        s.sb.blockSignals(False)

    def on_scrollbar(s, v):
        s.ox = float(v)
        s.update()

    def zoom_by(s, f, ax=None):
        if not s.segs:
            return
        ax = s.width() / 2 if ax is None else ax
        old = s.pps()
        # no lower bound tied to fit: zoom out freely
        new = max(1e-6, min(s.MAXZ, old * f))
        # time under the anchor stays put
        t = (ax - s.PAD + s.ox) / old
        s.z = new
        s.ox = s.PAD + t * new - ax
        s.sync()
        s.update()

    def fit_view(s):
        """Snapshot the current fit as a fixed zoom; nothing re-fits automatically after this."""
        s.z, s.ox = s.fit(), 0.0
        s.sync()
        s.update()

    def resizeEvent(s, e):
        super().resizeEvent(e)
        s.sync()

    def wheelEvent(s, ev):
        if not s.segs:
            return
        d = ev.angleDelta()
        if ev.modifiers() & Qt.ControlModifier:
            s.zoom_by(1.15 ** (d.y() / 120), ev.position().x())
        else:
            s.ox -= (d.x() or d.y())
            s.sync()
            s.update()
        ev.accept()

    def track(s, i, t):
        s.cur = i
        b, e = s.segs[i]
        s.head = s.offset(i) + min(max(t - b, 0), e - b)
        s.sync()
        s.update()

    def goto(s, i, t): s.track(i, t); s.seek.emit(i, t)

    def src(s):
        b, e = s.segs[s.cur]
        return s.cur, b + s.head - s.offset(s.cur)

    def scrub(s, x):
        t = max(0, min(s.total(), (x - s.PAD + s.ox) / s.pps()))
        acc = 0
        for i, (b, e) in enumerate(s.segs):
            if t <= acc + (e - b) or i == len(s.segs) - 1:
                s.track(i, min(e, b + t - acc))
                s.preview.emit(s.src()[1])
                return
            acc += e - b

    def commit_scrub(s):
        acc = 0
        for i, (b, e) in enumerate(s.segs):
            seg_len = e - b
            if s.head <= acc + seg_len or i == len(s.segs) - 1:
                s.goto(i, min(e, b + s.head - acc))
                return
            acc += seg_len

    def paintEvent(s, _):
        p = QPainter(s)
        p.setRenderHint(QPainter.Antialiasing)
        W, pps, tot = s.width(), s.pps(), s.total()
        p.fillRect(s.rect(), QColor("#1e1f22"))
        p.fillRect(QRectF(0, 0, W, s.RULER - 4), QColor("#2b2d31"))
        p.setPen(QColor("#888"))
        step = next((c for c in (0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800)
                     if c * pps >= 70), 3600)
        k = max(0, int((s.ox - s.PAD) / pps / step))
        while k * step <= tot + 1e-9:
            x = s.PAD - s.ox + k * step * pps
            if x > W:
                break
            p.drawLine(QPointF(x, 6), QPointF(x, s.RULER - 6))
            p.drawText(QPointF(x + 3, 13), f"{round(k * step, 2):g}s")
            k += 1
        view = QRectF(0, 0, W, s.height())
        for i, r in enumerate(s.rects()):
            if r.right() < 0 or r.left() > W:
                continue
            sel = i == s.cur
            p.setBrush(QColor("#3d8bfd") if sel else QColor("#4a5568"))
            p.setPen(QPen(QColor("white") if sel else QColor(
                "#222"), 2 if sel else 1))
            p.drawRoundedRect(r, 5, 5)
            p.setPen(Qt.white)
            b, e = s.segs[i]
            vr = r.intersected(view)
            p.drawText(vr.adjusted(8, 0, -8, 0),
                       Qt.AlignCenter, f"{e - b:.2f}s")
            p.fillRect(QRectF(r.left() + 1, r.top() + 8, 4,
                       r.height() - 16), QColor("#ffd54f"))
            p.fillRect(QRectF(r.right() - 5, r.top() + 8, 4,
                       r.height() - 16), QColor("#ffd54f"))
        x = s.PAD - s.ox + s.head * pps
        si, sh = s.lshift()
        if si is not None and si == s.cur:
            x += sh
        p.setPen(QPen(QColor("#ff4d4f"), 2))
        p.drawLine(QPointF(x, 0), QPointF(x, s.height() - s.SB))

    def hit(s, x, y):
        if y < s.RULER:
            return None, 'scrub'
        # check the selected clip first: adjacent clips share an edge, and without
        # this priority the previous clip's right edge always wins the trim grab
        rects = s.rects()
        order = [s.cur] + [i for i in range(len(rects)) if i != s.cur]
        for i in order:
            r = rects[i]
            if abs(x - r.left()) <= s.EDGE:
                return i, 'l'
            if abs(x - r.right()) <= s.EDGE:
                return i, 'r'
            if r.left() <= x <= r.right():
                return i, 'move'
        return None, 'scrub'

    def mousePressEvent(s, ev):
        x, y = ev.position().x(), ev.position().y()
        if ev.button() == Qt.MiddleButton:      # pan
            s.pan = (x, s.ox)
            s.setCursor(Qt.ClosedHandCursor)
            return
        if ev.button() != Qt.LeftButton or not s.segs:
            return
        s.before = copy.deepcopy(s.segs)
        i, mode = s.hit(x, y)
        if i is not None:
            s.cur = i
        s.drag = (mode, i, x, list(s.segs[i]) if i is not None else None)
        if mode == 'scrub':
            s.scrub(x)
        elif mode == 'move':
            s.scrub(x)
        s.update()

    def mouseMoveEvent(s, ev):
        x, y = ev.position().x(), ev.position().y()
        if s.pan:
            s.ox = s.pan[1] - (x - s.pan[0])
            s.sync()
            s.update()
            return
        if s.drag is None:
            _, m = s.hit(x, y) if s.segs else (0, 'scrub')
            s.setCursor(Qt.SizeHorCursor if m in 'lr' and m !=
                        'scrub' else Qt.ArrowCursor)
            return
        mode, i, x0, orig = s.drag
        d = (x - x0) / s.pps()
        if mode == 'scrub':
            s.scrub(x)
        elif mode == 'l':
            s.segs[i][0] = min(max(0, orig[0] + d), orig[1] - MIN)
            s.track(i, s.segs[i][0])
            s.preview.emit(s.segs[i][0])
        elif mode == 'r':
            s.segs[i][1] = max(min(s.dur, orig[1] + d), orig[0] + MIN)
            t = max(s.segs[i][0], s.segs[i][1] - 0.04)
            s.track(i, t)
            s.preview.emit(t)
        elif mode == 'move' and abs(x - x0) > 4:
            cx, n = s.PAD - s.ox, 0
            for k, (b, e) in enumerate(s.segs):
                if k == i:
                    continue
                w = (e - b) * s.pps()
                if cx + w / 2 < x:
                    n += 1
                cx += w
            if n != i:
                s.segs.insert(n, s.segs.pop(i))
                s.drag = (mode, n, x0, orig)
                s.cur = n
                s.head = s.offset(n)
            s.update()

    def mouseReleaseEvent(s, ev):
        if s.pan and ev.button() == Qt.MiddleButton:
            s.pan = None
            s.setCursor(Qt.ArrowCursor)
            return
        if s.drag is None:
            return
        mode = s.drag[0]
        if mode == 'scrub':
            x = ev.position().x()
            s.scrub(x)
            s.commit_scrub()
        elif mode in ('l', 'r'):
            # trim done: swap proxy for the real frame
            s.seek.emit(*s.src())
        elif mode == 'move':
            i, b = s.src()
            s.seek.emit(s.cur, b)
        s.drag = None
        if s.segs and s.segs != s.before:
            s.committed.emit(s.before)
            s.changed.emit()
        s.sync()
        s.update()
