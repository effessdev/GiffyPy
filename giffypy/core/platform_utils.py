# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""Shared helpers for suppressing console windows when launching bundled
ffmpeg-family binaries from a no-console packaged app on Windows."""

import os
import subprocess


def hidden_subprocess_kwargs(extra_creationflags=0):
    """Return subprocess.run/Popen kwargs that stop a console-subsystem
    child process (ffmpeg.exe, ffprobe.exe) from flashing a terminal
    window when launched from a GUI app built without a console.

    `extra_creationflags` lets a caller OR in additional Windows creation
    flags (e.g. CREATE_NEW_PROCESS_GROUP, needed to later send
    CTRL_BREAK_EVENT) without duplicating the STARTUPINFO setup.

    No-op (returns {}) on POSIX, where these constants don't exist.
    """
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return {
            "startupinfo": si,
            "creationflags": subprocess.CREATE_NO_WINDOW | extra_creationflags,
        }
    return {}
