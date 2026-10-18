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

    @property
    def is_recording(self):
        return self.process is not None and self.process.poll() is None

    @staticmethod
    def build_command(path, fps=30, ffmpeg_binary=None):
        ffmpeg_binary = ffmpeg_binary or FFMPEG or "ffmpeg"
        return [
            ffmpeg_binary,
            "-y",
            "-f",
            "gdigrab",
            "-framerate",
            str(int(fps)),
            "-i",
            "desktop",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            path,
        ]

    def start(self):
        if self.is_recording:
            return self.output_path

        self.output_path = os.path.join(self.output_dir, f"giffypy_record_{uuid4().hex}.mp4")
        cmd = self.build_command(self.output_path, fps=self.fps, ffmpeg_binary=FFMPEG)

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        return self.output_path

    def stop(self):
        if not self.process or self.process.poll() is not None:
            return self.output_path

        try:
            if os.name == "nt":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.process.send_signal(signal.SIGINT)
            self.process.wait(timeout=10)
        except (AttributeError, ValueError):
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        return self.output_path

    def discard(self):
        path = self.output_path
        self.output_path = None
        self.process = None
        if path and os.path.exists(path):
            os.remove(path)
        return path
