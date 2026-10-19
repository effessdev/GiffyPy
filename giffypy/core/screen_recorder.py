# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import os
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from .constants import FFMPEG, SCREEN_RECORDING_PREFIX
from .platform_utils import hidden_subprocess_kwargs

#: Screen capture currently only implements the Windows gdigrab path.
#: Other platforms would need avfoundation (macOS) / x11grab or pipewire
#: (Linux) backends in build_command before this can be enabled there.
SCREEN_RECORDING_SUPPORTED = sys.platform == "win32"


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
            "-draw_mouse",
            "1" if capture_cursor else "0",
            "-i",
            "desktop",
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
            "-t",
            "600",
            path,
        ])
        return cmd

    def start(self, capture_cursor=None):
        if self.is_recording:
            return self.output_path

        if capture_cursor is not None:
            self.capture_cursor = bool(capture_cursor)

        path = os.path.join(
            self.output_dir, f"{SCREEN_RECORDING_PREFIX}{uuid4().hex}.mp4")
        cmd = self.build_command(
            path, fps=self.fps, ffmpeg_binary=FFMPEG, capture_cursor=self.capture_cursor)

        popen_kwargs = hidden_subprocess_kwargs(
            extra_creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)

        self.output_path = path
        self.process = None
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # stdin must be a pipe (not DEVNULL) so stop() can send ffmpeg
                # a graceful "q" on Windows. Killing ffmpeg via CTRL_BREAK_EVENT
                # alone frequently truncates the MP4 before the moov atom is
                # written, leaving an unplayable file.
                stdin=subprocess.PIPE,
                **popen_kwargs,
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

    def _wait_for_valid_output(self, path, timeout=4.0):
        if not path:
            return False

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not os.path.exists(path):
                time.sleep(0.2)
                continue
            try:
                from .media import probe
                probe(path)
                return True
            except (FileNotFoundError, OSError, ValueError, subprocess.SubprocessError):
                time.sleep(0.2)
        return False

    def _graceful_stop(self, proc, timeout):
        """Ask ffmpeg to quit cleanly so it finalizes the output file.

        Writing 'q' to stdin is ffmpeg's documented graceful-shutdown path
        and is the most reliable way to get a valid MP4 out of it on
        Windows. CTRL_BREAK_EVENT is kept as a fallback for builds/consoles
        where stdin signaling doesn't work.
        """
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.write(b"q")
                proc.stdin.flush()
                proc.wait(timeout=timeout)
                return True
        except (BrokenPipeError, OSError, ValueError, subprocess.TimeoutExpired):
            pass

        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.send_signal(signal.SIGINT)
            proc.wait(timeout=timeout)
            return True
        except (AttributeError, ValueError, OSError, PermissionError, subprocess.TimeoutExpired):
            return False

    def stop(self):
        path = self.output_path
        proc = self.process

        if not proc or proc.poll() is not None:
            self.process = None
            self.output_path = None
            return path

        if not self._graceful_stop(proc, timeout=10):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except (OSError, ValueError):
            pass

        self.process = None
        self.output_path = None

        if path and self._wait_for_valid_output(path):
            return path
        return None

    def discard(self):
        path = self.output_path
        proc = self.process
        self.output_path = None
        self.process = None

        if proc and proc.poll() is None:
            # Must stop ffmpeg before touching the file: on Windows the
            # file is locked while ffmpeg holds it open, and os.remove()
            # would raise PermissionError. This also prevents leaving an
            # orphaned ffmpeg process running in the background.
            if not self._graceful_stop(proc, timeout=5):
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
            except (OSError, ValueError):
                pass

        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        return path
