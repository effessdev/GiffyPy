# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import os
import shutil
import subprocess
import tempfile
import threading
from PySide6.QtCore import Qt, QSizeF, QUrl, QTimer, QProcess, QEvent, Signal
from PySide6.QtGui import QColor, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QGraphicsPixmapItem,
    QGraphicsScene, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

from .core.constants import FFMPEG, FFPROBE, FPS_STEPS, PREVIEW_FPS, MIN, FILTER
from .ui.crop import CropItem, View
from .ui.timeline import Timeline
from .ui import apply_theme, build_export_panel, build_toolbar, update_toolbar_state
from .core.loader import MediaLoader
from .core.preview import PreviewManager
from .core.editor import EditorController
from .core.exporter import ExportController
from .core.screen_recorder import ScreenRecorder
from .core.session import reset_session as reset_session_controller


class PlaceholderWidget(QWidget):
    def __init__(self, parent, window):
        super().__init__(parent)
        self.window = window
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "PlaceholderWidget { background: transparent; border: none; }"
            "QLabel { color: #d0d0d0; background: transparent; }"
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.window.load(urls[0].toLocalFile())
            event.acceptProposedAction()


class Main(QMainWindow):
    # Emitted from the recorder-stop worker thread with the finalized path
    # (or None); queued delivery lands the handler back on the GUI thread.
    recording_stopped = Signal(object)

    def __init__(s):
        super().__init__()
        s.setWindowTitle("GiffyPy")
        s.setAcceptDrops(True)
        s.path, s.W, s.H, s.undo, s.crop, s.proxied = None, 0, 0, [], None, False
        s.busy = False
        s.load_token = 0
        s.recording_stopping = False
        s.rec_stop_thread = None
        s.screen_recorder = ScreenRecorder()
        s.recording_stopped.connect(s._on_recording_stopped)
        s.loader = MediaLoader(s)
        s.loader.finished.connect(s._load_complete)
        s.loader.failed.connect(s._load_failed)
        s.preview = PreviewManager(s)
        s.editor = EditorController(s)
        s.exporter = ExportController(s)
        s.speed_before = None
        s.prev_dir, s.prev_proc, s.prev_cache, s.pidx = None, None, {}, -1
        s.stale_prev_dirs = []
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
        except (AttributeError, RuntimeError):  # older PySide without QGraphicsVideoItem.videoSink()
            s.sink = None
        s.view = View(s.scene)
        s.placeholder = PlaceholderWidget(s.view.viewport(), s)
        s.placeholder_layout = QVBoxLayout(s.placeholder)
        s.placeholder_layout.setContentsMargins(28, 22, 28, 22)
        s.placeholder_layout.setSpacing(12)
        s.placeholder_layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("🎬")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 48px; background: transparent;")
        title = QLabel("Drag & Drop Video Here")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 20px; font-weight: 600; color: #e5e5e5; background: transparent;")
        s.open_file_btn = QPushButton("Open file")
        s.open_file_btn.setFocusPolicy(Qt.NoFocus)
        s.open_file_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        s.open_file_btn.setMinimumHeight(40)
        s.open_file_btn.clicked.connect(s.open)

        s.record_screen_btn = QPushButton("Record screen")
        s.record_screen_btn.setFocusPolicy(Qt.NoFocus)
        s.record_screen_btn.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed)
        s.record_screen_btn.setMinimumHeight(40)
        s.record_screen_btn.clicked.connect(s.toggle_screen_recording)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(12)
        actions.setAlignment(Qt.AlignCenter)
        actions.addWidget(s.open_file_btn, 1)
        actions.addWidget(s.record_screen_btn, 1)

        s.capture_cursor_checkbox = QCheckBox("Capture cursor")
        s.capture_cursor_checkbox.setChecked(False)
        s.capture_cursor_checkbox.setFocusPolicy(Qt.NoFocus)
        s.capture_cursor_checkbox.toggled.connect(s.on_capture_cursor_changed)

        s.placeholder_layout.addWidget(icon)
        s.placeholder_layout.addWidget(title)
        s.placeholder_layout.addLayout(actions)
        s.placeholder_layout.addSpacing(4)
        s.placeholder_layout.addWidget(
            s.capture_cursor_checkbox, 0, Qt.AlignCenter)
        s.placeholder.hide()
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

    def _build_toolbar(s):
        build_toolbar(s)

    def _build_export_panel(s):
        build_export_panel(s)

    def _apply_theme(s):
        apply_theme(s)

    def _install_shortcuts(s):
        for key, fn in (("Space", s.toggle_play), ("S", s.split), ("Delete", s.delete), ("Ctrl+Z", s.do_undo), ("Ctrl+O", s.open),
                        ("Left", lambda: s.step_frame(-1)
                         ), ("Right", lambda: s.step_frame(1)),
                        ("Ctrl+=", lambda: s.tl.zoom_by(1.5)
                         ), ("Ctrl++", lambda: s.tl.zoom_by(1.5)),
                        ("Ctrl+-", lambda: s.tl.zoom_by(1 / 1.5)), ("Ctrl+0", lambda: s.tl.fit_view())):
            QShortcut(QKeySequence(key), s, activated=fn)

    def _install_event_filters(s):
        # Keep the resize hook only; arrow keys are handled by dedicated shortcuts so the preview view does not pan or steal them.
        s.view.viewport().installEventFilter(s)
        QApplication.instance().installEventFilter(s)

    def toggle_export_panel(s):
        s.export_collapsed = not s.export_collapsed
        visible = not s.export_collapsed
        s.export_title.setVisible(visible)
        for w in s.export_controls:
            w.setVisible(visible)
        s.export_toggle.setText("▶" if s.export_collapsed else "◀")
        s.export_toggle.setToolTip(
            "Expand export panel" if s.export_collapsed else "Collapse export panel")
        s.export_panel.setFixedWidth(36 if s.export_collapsed else 250)
        s.export_panel.updateGeometry()

    def reset_session(s):
        reset_session_controller(s)

    # ---- loading
    def open(s):
        p, _ = QFileDialog.getOpenFileName(s, "Open video", "", FILTER)
        if p:
            s.load(p)

    def on_capture_cursor_changed(s, checked):
        s.screen_recorder.capture_cursor = bool(checked)

    def start_screen_recording(s):
        if not FFMPEG:
            s.status.setText(
                "⚠ ffmpeg/ffprobe not found — reinstall the app or add ffmpeg to PATH.")
            return
        if s.screen_recorder.is_recording:
            return

        s.screen_recorder.capture_cursor = s.capture_cursor_checkbox.isChecked()
        path = s.screen_recorder.start()
        if not path:
            s.record_screen_btn.setText("Record screen")
            s.status.setText(
                "⚠ Failed to start screen capture. Check that ffmpeg is available and try again.")
            return

        s.record_screen_btn.setText("Stop recording")
        s.status.setText(
            f"Recording whole display at 30 FPS → {os.path.basename(path)}")

    def stop_screen_recording(s):
        if s.screen_recorder is None or not s.screen_recorder.is_recording:
            return
        if s.recording_stopping:
            return

        s.recording_stopping = True
        s.record_screen_btn.setEnabled(False)
        s.record_screen_btn.setText("Stopping...")
        s.status.setText("Finalizing recording…")
        QApplication.processEvents()

        # ffmpeg finalization (~1s) runs off the GUI thread, like MediaLoader;
        # the recording_stopped signal hands the result back to the event loop.
        def worker():
            try:
                path = s.screen_recorder.stop()
            except (OSError, RuntimeError, subprocess.SubprocessError):
                path = None
            s.recording_stopped.emit(path)

        s.rec_stop_thread = threading.Thread(target=worker, daemon=True)
        s.rec_stop_thread.start()

    def _on_recording_stopped(s, path):
        s.recording_stopping = False
        s.rec_stop_thread = None
        s.record_screen_btn.setEnabled(True)
        s.record_screen_btn.setText("Record screen")

        if not path:
            s.status.setText("Recording ended without producing a file.")
            return

        msg = QMessageBox(s)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Recording finished")
        msg.setText(f"Screen recoding was saved to:\n\n{path}")
        load_btn = msg.addButton(
            "Open Screen Recording", QMessageBox.AcceptRole)
        discard_btn = msg.addButton("Discard", QMessageBox.DestructiveRole)
        msg.setDefaultButton(load_btn)
        msg.exec()

        if msg.clickedButton() is load_btn:
            s.status.setText(
                f"Loaded screen recording: {os.path.basename(path)}")
            s.load(path)
        else:
            s.screen_recorder.discard()
            s.status.setText("Screen recording discarded.")

    def toggle_screen_recording(s):
        if s.screen_recorder.is_recording:
            s.stop_screen_recording()
        else:
            s.start_screen_recording()

    def dragEnterEvent(s, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(s, e): s.load(e.mimeData().urls()[0].toLocalFile())

    def setup_placeholder(s):
        s.scene.setSceneRect(0, 0, 800, 450)
        s.vitem.hide()
        s.view.set_pan_enabled(False)
        s.placeholder.adjustSize()
        s.placeholder.setMinimumWidth(420)
        s.placeholder.setMaximumWidth(520)
        vp = s.view.viewport()
        s.placeholder.move((vp.width() - s.placeholder.width()) //
                           2, (vp.height() - s.placeholder.height()) // 2)
        s.placeholder.show()

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
        t = ev.type()
        if t == QEvent.Resize and obj is s.view.viewport() and s.placeholder is not None and not s.path:
            s.setup_placeholder()
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
        th = s.rec_stop_thread
        if th is not None and th.is_alive():
            # A normal stop is already finalizing off-thread; let its worker
            # finish so ffmpeg isn't orphaned mid-shutdown (the daemon thread
            # won't block exit).
            th.join(timeout=15)
        elif s.screen_recorder is not None and s.screen_recorder.is_recording:
            # Closing mid-capture: the async stop/signal path can't complete
            # during shutdown, so stop ffmpeg and delete the file here.
            # discard() both finalizes the process and removes the temp file,
            # leaving no orphaned ffmpeg or leftover capture behind.
            s.screen_recorder.discard()
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
        for d in list(s.stale_prev_dirs):
            shutil.rmtree(d, ignore_errors=True)
        s.stale_prev_dirs.clear()
        super().closeEvent(e)

    # ---- export
    def crop_rect(s):
        return s.exporter.crop_rect()

    def out_size(s):
        return s.exporter.out_size()

    def refresh(s):
        s.exporter.refresh()
        update_toolbar_state(s)

    def export(s, mode="numbered"):
        s.exporter.export(mode)

    def ffmpeg_args(s, dst):
        return s.exporter.ffmpeg_args(dst)

    def start_export(s, args):
        s.exporter.start_export(args)

    def on_prog(s):
        s.exporter.on_prog()

    def on_done(s, code, _):
        s.exporter.on_done(code, _)
