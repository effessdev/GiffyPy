import os
import tempfile

from PySide6.QtCore import QProcess, QUrl, QRectF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .constants import FFMPEG, FPS_STEPS
from .export import EXT_MAP, build_ffmpeg_args, next_numbered_export_path


class ExportController:
    def __init__(self, window):
        self.window = window

    def crop_rect(self):
        if self.window.crop and self.window.cropBtn.isChecked():
            r = self.window.crop.r
        else:
            r = QRectF(0, 0, self.window.W, self.window.H)
        return int(r.x()) // 2 * 2, int(r.y()) // 2 * 2, max(2, int(r.width()) // 2 * 2), max(2, int(r.height()) // 2 * 2)

    def out_size(self):
        _, _, w, h = self.crop_rect()
        k = self.window.scale.value() / 100
        return max(2, int(w * k) // 2 * 2), max(2, int(h * k) // 2 * 2)

    def refresh(self):
        self.window.sync_speed()
        fps = FPS_STEPS[self.window.fps.value()]
        W, H = self.out_size()
        tot = self.window.tl.total()
        self.window.fpsL.setText(f"Framerate: {fps:g} fps")
        self.window.scL.setText(f"Resolution: {self.window.scale.value()}%  ({W}×{H})")
        self.window.qL.setText(f"Quality: {self.window.q.value()}" +
                               ("  (colors)" if self.window.fmt.currentText() == "GIF" else ""))
        self.window.info.setText(f"{tot:.1f}s → ~{int(tot * fps)} frames")
        ready = bool(self.window.path and self.window.tl.segs) and not self.window.busy
        for b in (self.window.overBtn, self.window.numBtn, self.window.saveAsBtn):
            b.setEnabled(ready)

    def export(self, mode="numbered"):
        """mode: 'overwrite' | 'numbered' | 'saveas'"""
        if not (self.window.path and self.window.tl.segs and FFMPEG):
            return
        fmt = self.window.fmt.currentText()
        ext = EXT_MAP.get(fmt, ".mp4")
        base = os.path.splitext(self.window.path)[0]
        out = base + ext
        if mode == "saveas":
            out, _ = QFileDialog.getSaveFileName(
                self.window, "Save as", out, f"{fmt} (*{ext})")
            if not out:
                return
            if not out.lower().endswith(ext):
                out += ext
        elif mode == "numbered":
            out = next_numbered_export_path(self.window.path, ext)
        elif mode == "overwrite":
            if os.path.exists(out):
                msg = f"“{os.path.basename(out)}” already exists and will be replaced."
                if os.path.abspath(out) == os.path.abspath(self.window.path):
                    msg += "\n\nThis is your ORIGINAL source file."
                msg += "\n\nContinue?"
                if QMessageBox.question(self.window, "Overwrite existing file?", msg,
                                        QMessageBox.Yes | QMessageBox.No,
                                        QMessageBox.No) != QMessageBox.Yes:
                    return
        self.window.out = out
        self.window.tmp = f"{os.path.splitext(out)[0]}.__tmp__{ext}"
        self.start_export(self.ffmpeg_args(self.window.tmp))

    def ffmpeg_args(self, dst):
        return build_ffmpeg_args(
            src=self.window.path, dst=dst, fmt=self.window.fmt.currentText(), segs=self.window.tl.segs,
            crop=self.crop_rect(), src_size=(self.window.W, self.window.H), out_size=self.out_size(),
            fps=FPS_STEPS[self.window.fps.value()], q=self.window.q.value())

    def start_export(self, args):
        self.window.exp_total = self.window.tl.total()
        self.window.busy = True
        self.window.bar.setValue(0)
        self.refresh()
        self.window.status.setText("Exporting…")
        self.window.proc = QProcess(self.window)
        self.window.proc.readyReadStandardOutput.connect(self.on_prog)
        self.window.proc.finished.connect(self.on_done)
        self.window.proc.start(FFMPEG, args)

    def on_prog(self):
        for ln in bytes(self.window.proc.readAllStandardOutput()).decode(errors="ignore").splitlines():
            if ln.startswith(("out_time_us=", "out_time_ms=")):
                try:
                    t = int(ln.split("=")[1]) / 1e6
                except ValueError:
                    continue
                self.window.bar.setValue(min(99, int(100 * t / max(self.window.exp_total, 0.01))))

    def on_done(self, code, _):
        err = bytes(self.window.proc.readAllStandardError()).decode(errors="ignore")
        self.window.busy = False
        self.refresh()
        if code == 0 and os.path.exists(self.window.tmp):
            if os.path.abspath(self.window.out) == os.path.abspath(self.window.path):
                self.window.player.setSource(QUrl())
            try:
                os.replace(self.window.tmp, self.window.out)
                self.window.bar.setValue(100)
                self.window.status.setText(
                    f"✔ Saved {os.path.basename(self.window.out)} ({os.path.getsize(self.window.out) / 1e6:.2f} MB)")
            except OSError as ex:
                self.window.status.setText(f"Couldn't write output: {ex}")
        else:
            if os.path.exists(self.window.tmp):
                os.remove(self.window.tmp)
            self.window.status.setText("Export failed:\n" + err[-400:])
