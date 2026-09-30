#!/usr/bin/env python3
import sys
import os
import json
import shutil
import subprocess
import tempfile
import copy
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSizeF, QUrl, QTimer, QProcess
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QShortcut, QKeySequence, QDesktopServices
from PySide6.QtWidgets import *
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

FFMPEG, FFPROBE = shutil.which("ffmpeg"), shutil.which("ffprobe")
FPS_STEPS = [0.5, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 50, 60]
MIN = 0.05  # minimum clip length (s)
FILTER = ("Video (*.mp4 *.mkv *.mov *.webm *.avi *.flv *.ts *.m2ts *.m4v *.wmv *.mpg *.mpeg *.ogv *.3gp *.gif);;All files (*)")


def probe(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,duration:format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout)
    st = j["streams"][0]
    dur = 0.0
    for v in (j.get("format", {}).get("duration"), st.get("duration")):
        try:
            dur = float(v)
            break
        except (TypeError, ValueError):
            pass
    return int(st["width"]), int(st["height"]), dur


# ---------------------------------------------------------------- crop overlay
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


# -------------------------------------------------------------------- timeline
class Timeline(QWidget):
    """Clips laid out in edit order. Top strip = scrub, drag clip = reorder, drag clip edge = trim."""
    seek = Signal(int, float)      # clip index, source time
    committed = Signal(object)     # previous state (for undo)
    changed = Signal()
    PAD, EDGE, RULER, SB = 10, 7, 20, 14
    MAXZ = 4000.0  # max zoom (pixels per second)

    def __init__(s):
        super().__init__()
        s.segs, s.dur, s.cur, s.head, s.drag, s.fz = [], 0.0, 0, 0.0, None, None
        s.before, s.pan = [], None
        # auto = fit-to-width; z = px/sec; ox = scroll offset (px)
        s.auto, s.z, s.ox = True, 100.0, 0.0
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
        if s.fz:
            return s.fz
        return s.fit() if s.auto else s.z

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
        s.ox = 0.0 if (s.auto and not s.fz) else max(
            0.0, min(s.max_ox(), s.ox))
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

    def follow(s, chase=True):
        """Keep the playhead visible (used while playing / stepping)."""
        if chase and not s.auto and s.segs:
            vw = s.width() - 2 * s.PAD
            hx = s.head * s.pps()
            if hx < s.ox:
                s.ox = hx - vw * 0.1
            elif hx > s.ox + vw:
                s.ox = hx - vw * 0.9
        s.sync()

    def zoom_by(s, f, ax=None):
        if not s.segs or s.fz:
            return
        ax = s.width() / 2 if ax is None else ax
        old = s.pps()
        # no lower bound tied to fit: zoom out freely
        new = max(1e-6, min(s.MAXZ, old * f))
        # time under the anchor stays put
        t = (ax - s.PAD + s.ox) / old
        s.z = new
        s.auto = False
        s.ox = s.PAD + t * new - ax
        s.sync()
        s.update()

    def fit_view(s):
        s.auto, s.ox = True, 0.0
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
        s.follow(s.drag is None)
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
        for i, r in enumerate(s.rects()):
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
        s.fz = s.pps()
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
            s.head = max(0.0, min(s.total(), (x - s.PAD + s.ox) / s.pps()))
            s.update()
        elif mode == 'l':
            s.segs[i][0] = min(max(0, orig[0] + d), orig[1] - MIN)
            s.goto(i, s.segs[i][0])
        elif mode == 'r':
            s.segs[i][1] = max(min(s.dur, orig[1] + d), orig[0] + MIN)
            s.goto(i, max(s.segs[i][0], s.segs[i][1] - 0.04))
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
        elif mode == 'move':
            i, b = s.src()
            s.seek.emit(s.cur, b)
        s.drag, s.fz = None, None
        if s.segs and s.segs != s.before:
            s.committed.emit(s.before)
            s.changed.emit()
        s.sync()
        s.update()


# ------------------------------------------------------------------ main window
class Main(QMainWindow):
    def __init__(s):
        super().__init__()
        s.setWindowTitle("GiffyPy")
        s.resize(1200, 760)
        s.setAcceptDrops(True)
        s.path, s.W, s.H, s.undo, s.crop, s.proxied = None, 0, 0, [], None, False
        s.player = QMediaPlayer()
        s.vitem = QGraphicsVideoItem()
        s.player.setVideoOutput(s.vitem)
        s.scene = QGraphicsScene()
        s.scene.addItem(s.vitem)
        s.view = View(s.scene)
        s.view.setBackgroundBrush(QColor("#111"))
        s.view.setFrameShape(QFrame.NoFrame)
        s.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        s.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        s.tl = Timeline()
        s.tl.seek.connect(lambda i, t: s.player.setPosition(int(t * 1000)))
        s.tl.committed.connect(s.undo.append)
        s.tl.changed.connect(s.refresh)
        s.player.durationChanged.connect(s.on_duration)
        s.player.errorOccurred.connect(s.on_error)
        s.timer = QTimer(s)
        s.timer.setInterval(15)
        s.timer.timeout.connect(s.tick)
        s.timer.start()

        def btn(text, fn, tip="", checkable=False):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(fn)
            return b
        s.playBtn = btn("▶ Play", s.toggle_play, "Space")
        s.cropBtn = btn("⛶ Crop", s.toggle_crop, "Show crop rectangle", True)
        bar = QHBoxLayout()
        for b in (btn("📂 Open", s.open, "Ctrl+O"), s.playBtn, btn("✂ Split", s.split, "S"),
                  btn("🗑 Delete clip", s.delete, "Del"), btn(
                      "↶ Undo", s.do_undo, "Ctrl+Z"), s.cropBtn,
                  btn("Reset crop", lambda: s.crop and s.crop.reset()),
                  btn("🔍−", lambda: s.tl.zoom_by(1 / 1.5), "Zoom out (Ctrl+-)"),
                  btn("🔍+", lambda: s.tl.zoom_by(1.5), "Zoom in (Ctrl+=)"),
                  btn("Fit", lambda: s.tl.fit_view(), "Fit timeline (Ctrl+0)")):
            bar.addWidget(b)
        bar.addStretch()
        hint = QLabel(
            "Drag the top strip to scrub · drag a clip to reorder · drag clip edges to trim · S split · Del delete · "
            "Wheel scroll · Ctrl+Wheel zoom · middle-drag pan")
        hint.setStyleSheet("color:#888")
        left = QVBoxLayout()
        left.addWidget(s.view, 1)
        left.addLayout(bar)
        left.addWidget(s.tl)
        left.addWidget(hint)

        # export panel
        s.fmt = QComboBox()
        s.fmt.addItems(["WebP", "GIF", "MP4", "WebM", "MOV", "MKV"])
        s.fmt.currentIndexChanged.connect(s.refresh)

        def slider(lo, hi, v):
            sl = QSlider(Qt.Horizontal)
            sl.setRange(lo, hi)
            sl.setValue(v)
            sl.valueChanged.connect(s.refresh)
            return sl
        s.fps = slider(0, len(FPS_STEPS) - 1, FPS_STEPS.index(10))
        s.scale = slider(5, 100, 60)
        s.q = slider(1, 100, 75)
        s.fpsL, s.scL, s.qL, s.info = QLabel(), QLabel(), QLabel(), QLabel()
        s.over = QCheckBox(
            "Overwrite existing file\n(otherwise saves a numbered copy)")
        s.over.setChecked(True)
        s.exp = QPushButton("Export")
        s.exp.setObjectName("go")
        s.exp.setMinimumHeight(46)
        s.exp.clicked.connect(s.export)
        s.bar = QProgressBar()
        s.bar.setRange(0, 100)
        s.status = QLabel()
        s.status.setWordWrap(True)
        s.folder = btn("Open folder", lambda: s.path and QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.dirname(s.path))))
        right = QVBoxLayout()
        for w in (QLabel("<b>Export</b>"), s.fmt, s.fpsL, s.fps, s.scL, s.scale, s.qL, s.q, s.info, s.over, s.exp, s.status, s.folder):
            right.addWidget(w)
        right.addStretch()
        panel = QWidget()
        panel.setLayout(right)
        panel.setFixedWidth(250)
        root = QHBoxLayout()
        root.addLayout(left, 1)
        root.addWidget(panel)
        c = QWidget()
        c.setLayout(root)
        s.setCentralWidget(c)
        s.setStyleSheet("QWidget{background:#25272b;color:#ddd} QPushButton{padding:6px 10px;background:#3a3d44;border-radius:5px}"
                        "QPushButton:checked{background:#3d8bfd} #go{background:#2ea043;color:white;font-weight:bold;font-size:15px}"
                        "QGraphicsView{background:#111}")
        for key, fn in (("Space", s.toggle_play), ("S", s.split), ("Delete", s.delete), ("Ctrl+Z", s.do_undo), ("Ctrl+O", s.open),
                        ("Left", lambda: s.step_frame(-1)
                         ), ("Right", lambda: s.step_frame(1)),
                        ("Ctrl+=", lambda: s.tl.zoom_by(1.5)
                         ), ("Ctrl++", lambda: s.tl.zoom_by(1.5)),
                        ("Ctrl+-", lambda: s.tl.zoom_by(1 / 1.5)), ("Ctrl+0", lambda: s.tl.fit_view())):
            QShortcut(QKeySequence(key), s, activated=fn)
        s.refresh()
        if not FFMPEG or not FFPROBE:
            s.status.setText(
                "⚠ ffmpeg/ffprobe not found on PATH — install ffmpeg.")

    # ---- loading
    def open(s):
        p, _ = QFileDialog.getOpenFileName(s, "Open video", "", FILTER)
        if p:
            s.load(p)

    def dragEnterEvent(s, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(s, e): s.load(e.mimeData().urls()[0].toLocalFile())

    def load(s, path):
        if not FFPROBE:
            return
        try:
            W, H, dur = probe(path)
        except Exception as ex:
            s.status.setText(f"Can't read file: {ex}")
            return
        s.path, s.W, s.H, s.undo, s.proxied = path, W, H, [], False
        s.tl.segs, s.tl.dur = [], dur
        s.scene.setSceneRect(0, 0, W, H)
        s.vitem.setSize(QSizeF(W, H))
        if s.crop:
            s.scene.removeItem(s.crop)
        s.crop = CropItem(W, H, s.refresh)
        s.scene.addItem(s.crop)
        s.crop.setVisible(s.cropBtn.isChecked())
        s.player.setSource(QUrl.fromLocalFile(path))
        s.player.pause()
        s.view.fitInView(s.scene.sceneRect(), Qt.KeepAspectRatio)
        s.setWindowTitle(f"GiffyPy — {os.path.basename(path)}")
        s.status.setText("")
        s.bar.setValue(0)
        if dur > 0:
            s.init_segs(dur)

    def init_segs(s, dur):
        s.tl.dur = dur
        s.tl.segs = [[0.0, dur]]
        s.tl.fit_view()
        s.tl.goto(0, 0.0)
        s.refresh()

    def on_duration(s, ms):
        if ms > 0 and not s.tl.segs:
            s.init_segs(ms / 1000)

    def on_error(s, *_):  # Qt backend can't decode it -> transcode a light preview proxy
        if s.proxied or not s.path or not FFMPEG:
            s.status.setText("Preview failed: " + s.player.errorString())
            return
        s.proxied = True
        s.status.setText("Building preview proxy…")
        proxy = os.path.join(tempfile.gettempdir(), "giffypy_proxy.mp4")
        p = QProcess(s)
        p.finished.connect(lambda *_: (s.player.setSource(QUrl.fromLocalFile(proxy)),
                           s.player.pause(), s.status.setText("")))
        p.start(FFMPEG, ["-y", "-loglevel", "error", "-i", s.path, "-an", "-vf", "scale=-2:min(720\\,ih)", "-c:v", "libx264",
                         "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p", proxy])

    # ---- playback / editing
    def playing(s): return s.player.playbackState(
    ) == QMediaPlayer.PlayingState

    def step_frame(s, direction):
        if not s.tl.segs:
            return
        if s.playing():
            s.player.pause()
        fps = FPS_STEPS[s.fps.value()]
        dt = direction * (1.0 / fps)
        new_head = max(0.0, min(s.tl.total(), s.tl.head + dt))
        acc = 0.0
        for i, (b, e) in enumerate(s.tl.segs):
            seg_len = e - b
            if new_head <= acc + seg_len or i == len(s.tl.segs) - 1:
                s.tl.goto(i, min(e, b + new_head - acc))
                return
            acc += seg_len

    def toggle_play(s):
        if not s.tl.segs:
            return
        if s.playing():
            s.player.pause()
        else:
            if s.tl.head >= s.tl.total() - 0.03:
                s.tl.goto(0, s.tl.segs[0][0])
            s.player.play()

    def tick(s):
        s.playBtn.setText("⏸ Pause" if s.playing() else "▶ Play")
        if not s.tl.segs or not s.playing():
            return
        pos = s.player.position() / 1000
        i = s.tl.cur
        b, e = s.tl.segs[i]
        if pos >= e - 0.01:
            if i + 1 < len(s.tl.segs):
                nb = s.tl.segs[i + 1][0]
                if abs(nb - e) < 0.03:
                    s.tl.track(i + 1, nb)      # contiguous: no seek needed
                else:
                    s.tl.goto(i + 1, nb)
            else:
                s.player.pause()
                s.tl.track(i, e)
        else:
            s.tl.track(i, pos)

    def split(s):
        if not s.tl.segs:
            return
        i, p = s.tl.src()
        b, e = s.tl.segs[i]
        if not b + MIN < p < e - MIN:
            return
        s.undo.append(copy.deepcopy(s.tl.segs))
        s.tl.segs[i:i + 1] = [[b, p], [p, e]]
        s.tl.track(i + 1, p)
        s.refresh()

    def delete(s):
        if len(s.tl.segs) < 2:
            return
        s.undo.append(copy.deepcopy(s.tl.segs))
        s.tl.segs.pop(s.tl.cur)
        i = min(s.tl.cur, len(s.tl.segs) - 1)
        s.tl.goto(i, s.tl.segs[i][0])
        s.refresh()

    def do_undo(s):
        if not s.undo:
            return
        s.tl.segs = s.undo.pop()
        i = min(s.tl.cur, len(s.tl.segs) - 1)
        s.tl.goto(i, s.tl.segs[i][0])
        s.refresh()

    def toggle_crop(s):
        if s.crop:
            s.crop.setVisible(s.cropBtn.isChecked())
            s.refresh()

    # ---- export
    def crop_rect(s):
        r = s.crop.r if (s.crop and s.cropBtn.isChecked()
                         ) else QRectF(0, 0, s.W, s.H)
        return int(r.x()) // 2 * 2, int(r.y()) // 2 * 2, max(2, int(r.width()) // 2 * 2), max(2, int(r.height()) // 2 * 2)

    def out_size(s):
        _, _, w, h = s.crop_rect()
        k = s.scale.value() / 100
        return max(2, int(w * k) // 2 * 2), max(2, int(h * k) // 2 * 2)

    def refresh(s):
        fps = FPS_STEPS[s.fps.value()]
        W, H = s.out_size()
        tot = s.tl.total()
        s.fpsL.setText(f"Framerate: {fps:g} fps")
        s.scL.setText(f"Resolution: {s.scale.value()}%  ({W}×{H})")
        s.qL.setText(f"Quality: {s.q.value()}" +
                     ("  (colors)" if s.fmt.currentText() == "GIF" else ""))
        s.info.setText(f"{tot:.1f}s → ~{int(tot * fps)} frames")

    def export(s):
        if not (s.path and s.tl.segs and FFMPEG):
            return
        fmt = s.fmt.currentText()
        ext_map = {
            "WebP": ".webp",
            "GIF": ".gif",
            "MP4": ".mp4",
            "WebM": ".webm",
            "MOV": ".mov",
            "MKV": ".mkv",
        }
        ext = ext_map.get(fmt, ".mp4")
        base = os.path.splitext(s.path)[0]
        out = base + ext
        if os.path.exists(out) and not s.over.isChecked():
            n = 1
            while os.path.exists(f"{base} (edited {n}){ext}"):
                n += 1
            out = f"{base} (edited {n}){ext}"
        s.out, s.tmp = out, f"{base}.__tmp__{ext}"
        x, y, w, h = s.crop_rect()
        W, H = s.out_size()
        fps = FPS_STEPS[s.fps.value()]
        segs = s.tl.segs
        parts = [
            f"[0:v]trim=start={b:.4f}:end={e:.4f},setpts=PTS-STARTPTS[v{i}]" for i, (b, e) in enumerate(segs)]
        vf = ([f"crop={w}:{h}:{x}:{y}"] if (w, h) != (s.W, s.H)
              else []) + [f"fps={fps}", f"scale={W}:{H}:flags=lanczos"]
        fc = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(
            len(segs))) + f"concat=n={len(segs)}:v=1:a=0,{','.join(vf)}"
        q = s.q.value()
        if fmt == "GIF":
            colors = 16 + q * 240 // 100
            fc += f"[o];[o]split[a][b];[a]palettegen=max_colors={colors}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle[out]"
            enc = ["-loop", "0"]
        elif fmt == "WebP":
            fc += "[out]"
            enc = ["-c:v", "libwebp_anim", "-lossless", "0", "-q:v",
                   str(q), "-compression_level", "4", "-loop", "0"]
        elif fmt == "WebM":
            fc += "[out]"
            crf = int(63 - q * 48 / 100)
            enc = ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0"]
        else:  # MP4, MOV, MKV
            fc += "[out]"
            crf = int(51 - q * 33 / 100)
            enc = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf)]
        s.exp_total = s.tl.total()
        s.bar.setValue(0)
        s.exp.setEnabled(False)
        s.status.setText("Exporting…")
        s.proc = QProcess(s)
        s.proc.readyReadStandardOutput.connect(s.on_prog)
        s.proc.finished.connect(s.on_done)
        s.proc.start(FFMPEG, ["-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats", "-i", s.path,
                              "-filter_complex", fc, "-map", "[out]", "-an", *enc, s.tmp])

    def on_prog(s):
        for ln in bytes(s.proc.readAllStandardOutput()).decode(errors="ignore").splitlines():
            if ln.startswith(("out_time_us=", "out_time_ms=")):
                try:
                    t = int(ln.split("=")[1]) / 1e6
                except ValueError:
                    continue
                s.bar.setValue(min(99, int(100 * t / max(s.exp_total, 0.01))))

    def on_done(s, code, _):
        err = bytes(s.proc.readAllStandardError()).decode(errors="ignore")
        s.exp.setEnabled(True)
        if code == 0 and os.path.exists(s.tmp):
            if os.path.abspath(s.out) == os.path.abspath(s.path):
                s.player.setSource(QUrl())  # release file (Windows)
            try:
                os.replace(s.tmp, s.out)
                s.bar.setValue(100)
                s.status.setText(
                    f"✔ Saved {os.path.basename(s.out)} ({os.path.getsize(s.out) / 1e6:.2f} MB)")
            except OSError as ex:
                s.status.setText(f"Couldn't write output: {ex}")
        else:
            if os.path.exists(s.tmp):
                os.remove(s.tmp)
            s.status.setText("Export failed:\n" + err[-400:])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Main()
    w.show()
    if len(sys.argv) > 1:
        w.load(sys.argv[1])
    sys.exit(app.exec())
