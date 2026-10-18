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

import os
import shutil
import tempfile
import copy
from PySide6.QtCore import Qt, QRectF, QSizeF, QUrl, QTimer, QProcess, QEvent
from PySide6.QtGui import QColor, QShortcut, QKeySequence, QDesktopServices, QImage, QPixmap, QCursor
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QGraphicsPixmapItem,
                               QGraphicsScene, QGraphicsTextItem, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QProgressBar, QPushButton, QSlider, QToolTip, QVBoxLayout, QWidget)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

from .constants import FFMPEG, FFPROBE, FPS_STEPS, PREVIEW_FPS, MIN, FILTER, CLIP_FMTS
from .export import EXT_MAP, build_ffmpeg_args, next_numbered_export_path
from .crop import CropItem, View
from .timeline import Timeline
from .ui import apply_theme, build_export_panel, build_toolbar
from .loader import MediaLoader
from .preview import PreviewManager
from .editor import EditorController
from .exporter import ExportController


class Main(QMainWindow):
    def __init__(s):
        super().__init__()
        s.setWindowTitle("GiffyPy")
        s.setAcceptDrops(True)
        s.path, s.W, s.H, s.undo, s.crop, s.proxied = None, 0, 0, [], None, False
        s.clip_mode, s.busy = False, False
        s.load_token = 0
        s.loader = MediaLoader(s)
        s.loader.finished.connect(s._load_complete)
        s.loader.failed.connect(s._load_failed)
        s.preview = PreviewManager(s)
        s.editor = EditorController(s)
        s.exporter = ExportController(s)
        s.speed_before = None
        s.prev_dir, s.prev_proc, s.prev_cache, s.pidx = None, None, {}, -1
        s.src_fps, s.prev_fps = 0.0, float(PREVIEW_FPS)

        s._init_media()
        s._init_scene_and_view()
        s._init_timeline()
        s._init_timers()
        s._build_export_panel()
        s._build_toolbar()
        s._apply_theme()
        s._install_shortcuts()
        s._install_event_filters()
        s.refresh()
        if not FFMPEG or not FFPROBE:
            s.status.setText(
                "⚠ ffmpeg/ffprobe not found — reinstall the app or add ffmpeg to PATH.")

    def _init_media(s):
        s.player = QMediaPlayer()
        s.vitem = QGraphicsVideoItem()
        s.player.setVideoOutput(s.vitem)

    def _init_scene_and_view(s):
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
            "<span style='font-size: 14px; color: #888;'>or click here to select a file</span>"
            "</div>"
        )
        s.scene.addItem(s.placeholder)
        s.view = View(s.scene)
        s.view.setBackgroundBrush(QColor("#111"))
        s.view.setFrameShape(QFrame.NoFrame)
        s.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        s.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        s.setup_placeholder()

    def _init_timeline(s):
        s.tl = Timeline()
        s.tl.seek.connect(s.on_seek)
        s.tl.preview.connect(s.show_preview)
        s.tl.committed.connect(s.undo.append)
        s.tl.changed.connect(s.refresh)
        s.tl.selected.connect(s.on_sel)
        s.player.durationChanged.connect(s.on_duration)
        s.player.errorOccurred.connect(s.on_error)

    def _init_timers(s):
        s.timer = QTimer(s)
        s.timer.setInterval(15)
        s.timer.timeout.connect(s.tick)
        s.timer.start()

    def _button(s, text, fn, tip="", checkable=False):
        b = QPushButton(text)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setFocusPolicy(Qt.NoFocus)
        b.clicked.connect(fn)
        return b

    def _range_slider(s, lo, hi, value, callback):
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(value)
        sl.valueChanged.connect(callback)
        return sl

    def _export_button(s, text, name, tip, fn):
        b = QPushButton(text)
        b.setObjectName(name)
        b.setMinimumHeight(40)
        b.setToolTip(tip)
        b.clicked.connect(fn)
        return b

    def _build_toolbar(s):
        build_toolbar(s)

    def _build_export_panel(s):
        build_export_panel(s)

    def _apply_theme(s):
        apply_theme(s)

    def _install_shortcuts(s):
        for key, fn in (("Space", s.toggle_play), ("S", s.split), ("Delete", s.delete), ("Ctrl+Z", s.do_undo), ("Ctrl+O", s.open),
                        ("Ctrl+=", lambda: s.tl.zoom_by(1.5)), ("Ctrl++", lambda: s.tl.zoom_by(1.5)),
                        ("Ctrl+-", lambda: s.tl.zoom_by(1 / 1.5)), ("Ctrl+0", lambda: s.tl.fit_view())):
            QShortcut(QKeySequence(key), s, activated=fn)

    def _install_event_filters(s):
        # Left/Right arrow keys step frames via eventFilter (proxy while held, real frame on release)
        s.view.viewport().installEventFilter(s)
        QApplication.instance().installEventFilter(s)

    def toggle_export_panel(s):
        s.export_collapsed = not s.export_collapsed
        visible = not s.export_collapsed
        s.export_title.setVisible(visible)
        for w in s.export_controls:
            w.setVisible(visible)
        s.export_toggle.setText("▶" if s.export_collapsed else "◀")
        s.export_toggle.setToolTip("Expand export panel" if s.export_collapsed else "Collapse export panel")
        s.export_panel.setFixedWidth(36 if s.export_collapsed else 250)
        s.export_panel.updateGeometry()

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
        s.view.set_pan_enabled(False)
        s.placeholder.show()
        s.placeholder.setTextWidth(500)
        br = s.placeholder.boundingRect()
        s.placeholder.setPos((800 - br.width()) / 2, (450 - br.height()) / 2)

    def load(s, path):
        s.loader.load(path)

    def _load_failed(s, token, path, ex):
        if token != s.load_token:
            return
        s.status.setText(f"Can't read file: {ex}")
        s.busy = False
        s.path = None
        s.view.set_pan_enabled(False)

    def _load_complete(s, token, path, W, H, dur, fps):
        if token != s.load_token:
            return
        s.placeholder.hide()
        s.vitem.show()
        s.path, s.W, s.H, s.undo, s.proxied = path, W, H, [], False
        s.view.set_pan_enabled(True)
        s.src_fps = fps
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
        s.view.fit_initial()
        s.setWindowTitle(f"GiffyPy — {os.path.basename(path)}")
        s.status.setText("")
        s.bar.setValue(0)
        s.busy = False
        s.start_preview(path)
        if dur > 0:
            s.init_segs(dur)

    def init_segs(s, dur):
        s.tl.dur = dur
        s.tl.segs = [[0.0, dur, 1.0]]
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
    def _clear_prev_proc(s, proc=None):
        s.preview._clear_prev_proc(proc)

    def _preview_proc_running(s):
        return s.preview._preview_proc_running()

    def start_preview(s, path):
        s.preview.start_preview(path)

    def show_preview(s, t):
        s.preview.show_preview(t)

    def on_seek(s, i, t):
        s.preview.on_seek(i, t)

    def on_real_frame(s, *_):
        s.preview.on_real_frame(*_)

    # ---- playback / editing
    def playing(s):
        return s.editor.playing()

    def step_frame(s, direction):
        s.editor.step_frame(direction)

    def commit_step(s):
        s.editor.commit_step()

    def eventFilter(s, obj, ev):
        """Left/Right arrows: preview-only while held; seek once on release."""
        t = ev.type()
        if t == QEvent.MouseButtonPress and obj is s.view.viewport() and not s.path and not s.busy:
            s.open()
            return True
        if t in (QEvent.KeyPress, QEvent.KeyRelease) and ev.key() in (Qt.Key_Left, Qt.Key_Right):
            w = obj if isinstance(obj, QWidget) else None
            if w is not None and (w is s or s.isAncestorOf(w)):
                if t == QEvent.KeyPress:
                    s.step_frame(-1 if ev.key() == Qt.Key_Left else 1)
                elif not ev.isAutoRepeat():
                    s.commit_step()
                return True
        return super().eventFilter(obj, ev)

    def toggle_play(s):
        s.editor.toggle_play()

    def tick(s):
        s.editor.tick()

    def split(s):
        s.editor.split()

    def delete(s):
        s.editor.delete()

    def do_undo(s):
        s.editor.do_undo()

    def on_sel(s, i):
        s.editor.on_sel(i)

    def sync_speed(s):
        s.editor.sync_speed()

    def on_speed_press(s):
        s.editor.on_speed_press()

    def on_speed(s, v):
        s.editor.on_speed(v)

    def on_speed_release(s):
        s.editor.on_speed_release()

    def toggle_crop(s):
        s.editor.toggle_crop()

    def closeEvent(s, e):
        proc = s.prev_proc
        if proc is not None:
            try:
                if proc.state() != QProcess.NotRunning:
                    proc.kill()
                    proc.waitForFinished(2000)
            except RuntimeError:
                pass
            finally:
                s._clear_prev_proc(proc)
        if s.prev_dir:
            shutil.rmtree(s.prev_dir, ignore_errors=True)
        super().closeEvent(e)

    # ---- export
    def crop_rect(s):
        return s.exporter.crop_rect()

    def out_size(s):
        return s.exporter.out_size()

    def refresh(s):
        s.exporter.refresh()

    def export(s, mode="numbered"):
        s.exporter.export(mode)

    def copy_to_clipboard(s):
        s.exporter.copy_to_clipboard()

    def ffmpeg_args(s, dst):
        return s.exporter.ffmpeg_args(dst)

    def start_export(s, args):
        s.exporter.start_export(args)

    def on_prog(s):
        s.exporter.on_prog()

    def on_done(s, code, _):
        s.exporter.on_done(code, _)
