import os
import shutil
import tempfile
import copy
from PySide6.QtCore import Qt, QRectF, QSizeF, QUrl, QTimer, QProcess
from PySide6.QtGui import QColor, QShortcut, QKeySequence, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QGraphicsPixmapItem,
                               QGraphicsScene, QGraphicsTextItem, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QProgressBar, QPushButton, QSlider, QVBoxLayout, QWidget)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

from .constants import FFMPEG, FFPROBE, FPS_STEPS, PREVIEW_FPS, PREVIEW_H, MIN, FILTER, CLIP_FMTS
from .media import probe
from .export import EXT_MAP, build_ffmpeg_args
from .crop import CropItem, View
from .timeline import Timeline


class Main(QMainWindow):
    def __init__(s):
        super().__init__()
        s.setWindowTitle("GiffyPy")
        s.setAcceptDrops(True)
        s.path, s.W, s.H, s.undo, s.crop, s.proxied = None, 0, 0, [], None, False
        s.clip_mode, s.busy = False, False
        s.prev_dir, s.prev_proc, s.prev_cache, s.pidx = None, None, {}, -1
        s.src_fps, s.prev_fps = 0.0, float(PREVIEW_FPS)
        s.player = QMediaPlayer()
        s.vitem = QGraphicsVideoItem()
        s.player.setVideoOutput(s.vitem)
        s.scene = QGraphicsScene()
        s.scene.addItem(s.vitem)
        s.pitem = QGraphicsPixmapItem()  # live-scrub proxy frame, layered over the video
        s.pitem.setZValue(0.5)
        s.pitem.hide()
        s.scene.addItem(s.pitem)
        s.sink = None
        try:
            s.sink = s.vitem.videoSink()
            # Python name is videoFrameChanged; frameObserved is the C++ alias
            getattr(s.sink, 'videoFrameChanged', None).connect(s.on_real_frame)
        except Exception:  # older PySide without QGraphicsVideoItem.videoSink()
            s.sink = None
        s.placeholder = QGraphicsTextItem()
        s.placeholder.setHtml(
            "<div style='text-align: center;'>"
            "<span style='font-size: 48px;'>🎬</span><br><br>"
            "<span style='font-size: 20px; font-weight: bold; color: #ccc;'>Drag & Drop Video Here</span><br><br>"
            "<span style='font-size: 14px; color: #888;'>or click <b>📂 Open</b> to select a file</span>"
            "</div>"
        )
        s.scene.addItem(s.placeholder)
        s.setup_placeholder()
        s.view = View(s.scene)
        s.view.setBackgroundBrush(QColor("#111"))
        s.view.setFrameShape(QFrame.NoFrame)
        s.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        s.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        s.tl = Timeline()
        s.tl.seek.connect(s.on_seek)
        s.tl.preview.connect(s.show_preview)
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

        def exp_btn(text, name, tip, fn):
            b = QPushButton(text)
            b.setObjectName(name)
            b.setMinimumHeight(40)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            return b
        s.overBtn = exp_btn("Overwrite Existing File", "ow",
                            "Save next to the source video, replacing any existing file (asks to confirm)",
                            lambda: s.export("overwrite"))
        s.numBtn = exp_btn("Save a Numbered Copy", "go",
                           "Save next to the source video as \"name (edited N)\" without replacing anything",
                           lambda: s.export("numbered"))
        s.saveAsBtn = exp_btn("Save To…", "sa",
                              "Choose where to save the file",
                              lambda: s.export("saveas"))
        s.clipBtn = exp_btn("Copy to Clipboard", "cp",
                            "Export and copy to clipboard (only GIF / WebP support this)",
                            s.copy_to_clipboard)
        s.bar = QProgressBar()
        s.bar.setRange(0, 100)
        s.status = QLabel()
        s.status.setWordWrap(True)
        s.folder = btn("Open folder", lambda: s.path and QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.dirname(s.path))))
        right = QVBoxLayout()
        for w in (QLabel("<b>Export</b>"), s.fmt, s.fpsL, s.fps, s.scL, s.scale, s.qL, s.q, s.info,
                  s.overBtn, s.numBtn, s.saveAsBtn, s.clipBtn, s.status, s.folder):
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
                        "QPushButton:disabled{background:#2b2d30;color:#555}"
                        "QPushButton:checked{background:#3d8bfd}"
                        "#ow,#go,#sa,#cp{color:white;font-weight:bold;font-size:13px}"
                        "#ow{background:#d9822b} #go{background:#2ea043} #sa{background:#3d8bfd} #cp{background:#8957e5}"
                        "#ow:disabled,#go:disabled,#sa:disabled,#cp:disabled{background:#2b2d30;color:#555}"
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

    def setup_placeholder(s):
        s.scene.setSceneRect(0, 0, 800, 450)
        s.vitem.hide()
        s.placeholder.show()
        s.placeholder.setTextWidth(500)
        br = s.placeholder.boundingRect()
        s.placeholder.setPos((800 - br.width()) / 2, (450 - br.height()) / 2)

    def load(s, path):
        if not FFPROBE:
            return
        try:
            W, H, dur, s.src_fps = probe(path)
        except Exception as ex:
            s.status.setText(f"Can't read file: {ex}")
            return
        s.placeholder.hide()
        s.vitem.show()
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
        s.start_preview(path)
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

    # ---- live preview (low-res image sequence for instant scrubbing)
    def start_preview(s, path):
        """Generate a small JPEG sequence in the background: scrub = O(1) file read, no decoding."""
        if s.prev_proc and s.prev_proc.state() != QProcess.NotRunning:
            s.prev_proc.kill()
            s.prev_proc.waitForFinished(2000)
        old, s.prev_dir, s.prev_cache, s.pidx = s.prev_dir, None, {}, -1
        s.pitem.hide()
        if not FFMPEG:
            return
        s.prev_dir = tempfile.mkdtemp(prefix="giffypy_prev_")
        out = os.path.join(s.prev_dir, "f%06d.jpg")
        s.prev_proc = QProcess(s)
        s.prev_proc.finished.connect(
            lambda *_, o=s.prev_proc: (o.deleteLater(),
                                       s.status.setText("") if s.status.text() == "Building live preview…" else None))
        if old:
            QTimer.singleShot(1000, lambda: shutil.rmtree(
                old, ignore_errors=True))
        s.status.setText("Building live preview…")
        # match the source frame rate 1:1 so every proxy frame is a real source frame
        s.prev_fps = min(
            240.0, s.src_fps) if s.src_fps > 0 else float(PREVIEW_FPS)
        s.prev_proc.start(FFMPEG, ["-y", "-loglevel", "error", "-i", path, "-an", "-vf",
                                   f"scale=-2:min({PREVIEW_H}\\,ih)", "-r", f"{s.prev_fps:.9g}",
                                   "-q:v", "4", out])

    def show_preview(s, t):
        """Paint the proxy frame nearest source time t over the (slow) video item."""
        if not (s.prev_dir and s.H) or s.playing():
            return
        idx = max(1, int(round(max(0.0, t) * s.prev_fps)) + 1)
        if s.pidx == idx and s.pitem.isVisible():
            return
        pm = s.prev_cache.get(idx)
        if pm is None:
            img = QImage(os.path.join(s.prev_dir, f"f{idx:06d}.jpg"))
            if img.isNull():  # not generated yet
                return
            pm = QPixmap.fromImage(img)
            if len(s.prev_cache) > 120:
                s.prev_cache.clear()
            s.prev_cache[idx] = pm
        s.pidx = idx
        s.pitem.setPixmap(pm)
        s.pitem.setScale(s.H / pm.height())
        s.pitem.show()

    def on_seek(s, i, t):
        s.player.setPosition(int(t * 1000))
        if not s.playing():
            # instant rough frame; swapped out when the real one lands
            s.show_preview(t)
            if s.sink is None:  # no way to observe the real frame -> hide after a beat
                QTimer.singleShot(300, s.pitem.hide)

    def on_real_frame(s, *_):
        """QVideoSink delivered a freshly decoded frame -> retire the proxy."""
        if not s.playing():
            s.pitem.hide()

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
            s.pitem.hide()
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

    def closeEvent(s, e):
        if s.prev_proc and s.prev_proc.state() != QProcess.NotRunning:
            s.prev_proc.kill()
        if s.prev_dir:
            shutil.rmtree(s.prev_dir, ignore_errors=True)
        super().closeEvent(e)

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
        ready = bool(s.path and s.tl.segs) and not s.busy
        for b in (s.overBtn, s.numBtn, s.saveAsBtn):
            b.setEnabled(ready)
        s.clipBtn.setEnabled(ready and s.fmt.currentText() in CLIP_FMTS)

    def export(s, mode="numbered"):
        """mode: 'overwrite' | 'numbered' | 'saveas'"""
        if not (s.path and s.tl.segs and FFMPEG):
            return
        fmt = s.fmt.currentText()
        ext = EXT_MAP.get(fmt, ".mp4")
        base = os.path.splitext(s.path)[0]
        out = base + ext
        if mode == "saveas":
            out, _ = QFileDialog.getSaveFileName(
                s, "Save as", out, f"{fmt} (*{ext})")
            if not out:
                return
            if not out.lower().endswith(ext):
                out += ext
        elif mode == "numbered":
            if os.path.exists(out):
                n = 1
                while os.path.exists(f"{base} (edited {n}){ext}"):
                    n += 1
                out = f"{base} (edited {n}){ext}"
        elif mode == "overwrite":
            if os.path.exists(out):
                msg = f"“{os.path.basename(out)}” already exists and will be replaced."
                if os.path.abspath(out) == os.path.abspath(s.path):
                    msg += "\n\nThis is your ORIGINAL source file."
                msg += "\n\nContinue?"
                if QMessageBox.question(s, "Overwrite existing file?", msg,
                                        QMessageBox.Yes | QMessageBox.No,
                                        QMessageBox.No) != QMessageBox.Yes:
                    return
        s.out = out
        s.tmp = f"{os.path.splitext(out)[0]}.__tmp__{ext}"
        s.clip_mode = False
        s.start_export(s.ffmpeg_args(s.tmp))

    def copy_to_clipboard(s):
        """Export to a temp file behind the scenes, then put the result on the clipboard."""
        if not (s.path and s.tl.segs and FFMPEG) or s.fmt.currentText() not in CLIP_FMTS:
            return
        ext = ".webp" if s.fmt.currentText() == "WebP" else ".gif"
        s.tmp = os.path.join(tempfile.gettempdir(),
                             f"giffypy_clip_{os.path.splitext(os.path.basename(s.path))[0]}{ext}")
        s.out = s.tmp
        s.clip_mode = True
        s.start_export(s.ffmpeg_args(s.tmp))

    def ffmpeg_args(s, dst):
        return build_ffmpeg_args(
            src=s.path, dst=dst, fmt=s.fmt.currentText(), segs=s.tl.segs,
            crop=s.crop_rect(), src_size=(s.W, s.H), out_size=s.out_size(),
            fps=FPS_STEPS[s.fps.value()], q=s.q.value())

    def start_export(s, args):
        s.exp_total = s.tl.total()
        s.busy = True
        s.bar.setValue(0)
        s.refresh()
        s.status.setText(
            "Copying to clipboard…" if s.clip_mode else "Exporting…")
        s.proc = QProcess(s)
        s.proc.readyReadStandardOutput.connect(s.on_prog)
        s.proc.finished.connect(s.on_done)
        s.proc.start(FFMPEG, args)

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
        s.busy = False
        s.refresh()
        if code == 0 and os.path.exists(s.tmp):
            if s.clip_mode:
                img = QImage(s.tmp)
                os.remove(s.tmp)
                if img.isNull():
                    s.status.setText(
                        "Couldn't copy to clipboard: exported file unreadable.")
                else:
                    QApplication.clipboard().setImage(img)
                    s.bar.setValue(100)
                    s.status.setText(
                        f"✔ Copied {s.fmt.currentText()} to clipboard")
            else:
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
