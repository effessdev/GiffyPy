import os
import signal
import subprocess
import tempfile
from uuid import uuid4

from .constants import FFMPEG


class ScreenRecorder:
    """Owns desktop capture so the main window stays simple."""

    def __init__(self, fps=30, output_dir=None):
        self.fps = int(fps)
        self.output_dir = output_dir or tempfile.gettempdir()
        self.process = None
        self.output_path = None
        self.capture_cursor = False

    @property
    def is_recording(self):
        return self.process is not None and self.process.poll() is None

    @staticmethod
    def build_command(path, fps=30, ffmpeg_binary=None, capture_cursor=False):
        ffmpeg_binary = ffmpeg_binary or FFMPEG or "ffmpeg"
        cmd = [
            ffmpeg_binary,
            "-y",
            "-f",
            "gdigrab",
            "-framerate",
            str(int(fps)),
            "-i",
            "desktop",
            "-draw_mouse",
            "1" if capture_cursor else "0",
        ]
        cmd.extend([
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            path,
        ])
        return cmd

    def start(self, capture_cursor=None):
        if self.is_recording:
            return self.output_path

        if capture_cursor is not None:
            self.capture_cursor = bool(capture_cursor)

        path = os.path.join(self.output_dir, f"giffypy_record_{uuid4().hex}.mp4")
        cmd = self.build_command(path, fps=self.fps, ffmpeg_binary=FFMPEG, capture_cursor=self.capture_cursor)

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        self.output_path = path
        self.process = None
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        except OSError:
            self.output_path = None
            self.process = None
            return None

        if self.process.poll() is not None:
            self.output_path = None
            self.process = None
            return None

        return self.output_path

    def stop(self):
        path = self.output_path
        proc = self.process
        self.process = None
        self.output_path = None

        if not proc or proc.poll() is not None:
            return path

        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.send_signal(signal.SIGINT)
            proc.wait(timeout=10)
        except (AttributeError, ValueError):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        return path

    def discard(self):
        path = self.output_path
        self.output_path = None
        self.process = None
        if path and os.path.exists(path):
            os.remove(path)
        return path
