# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

import os
import shutil
import sys


def find_binary(name):
    """Return the bundled ffmpeg-family binary if present, else the PATH one."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        exe = os.path.join(bundled, f"{name}.exe")
        if os.path.exists(exe):
            return exe
    return shutil.which(name)


FFMPEG, FFPROBE = find_binary("ffmpeg"), find_binary("ffprobe")
FPS_STEPS = [0.5, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 50, 60]
# low-res image sequence for instant scrub preview; PREVIEW_FPS is the fallback seq rate
# used only when the source frame rate can't be probed (some GIFs / VFR files)
PREVIEW_FPS, PREVIEW_H = 12, 480
SCREEN_RECORDING_PREFIX = "giffypy_record_"
MIN = 0.05  # minimum clip length (s)
# clip speed range, shared by the slider and preview playback
SPEED_MIN, SPEED_MAX = 0.1, 4.0
FILTER = ("Video (*.mp4 *.mkv *.mov *.webm *.avi *.flv *.ts *.m2ts *.m4v *.wmv *.mpg *.mpeg *.ogv *.3gp *.gif);;All files (*)")
