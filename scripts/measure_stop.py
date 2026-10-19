#!/usr/bin/env python3

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

"""Record a 10-second screen capture and log how long stopping takes.

Every internal step of ScreenRecorder.stop() is instrumented with elapsed
timings so the shutdown path (graceful 'q', process reap, output validation)
can be profiled. Run from the repo root:

    python scripts/measure_stop.py
"""

import logging
import os
import sys
import time

# Allow running directly from the scripts/ folder by putting the repo root
# on sys.path before importing the package.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from giffypy.screen_recorder import ScreenRecorder  # noqa: E402

RECORD_SECONDS = 10

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("measure_stop")


def timed(label, fn):
    """Call fn and log how long it took. Returns (result, elapsed_seconds)."""
    log.info(f"calling {label} ...")
    start = time.perf_counter()
    try:
        result = fn()
    except BaseException as exc:  # re-log failures with timing context
        elapsed = time.perf_counter() - start
        log.exception(f"{label} raised {exc!r} after {elapsed:.3f}s")
        raise
    elapsed = time.perf_counter() - start
    log.info(f"{label} returned {result!r} after {elapsed:.3f}s")
    return result, elapsed


class TimedScreenRecorder(ScreenRecorder):
    """ScreenRecorder that logs the duration of every stop-related step.

    Zero-arg `super()` only works directly inside a method body, not in a
    lambda, so each parent method is bound to a local name first and the
    lambda calls it with an explicit `self`.
    """

    def start(self, capture_cursor=None):
        parent = ScreenRecorder.start
        result, _ = timed("ScreenRecorder.start",
                          lambda: parent(self, capture_cursor))
        return result

    def _graceful_stop(self, proc, timeout):
        parent = ScreenRecorder._graceful_stop
        result, _ = timed(
            f"ScreenRecorder._graceful_stop(timeout={timeout})",
            lambda: parent(self, proc, timeout),
        )
        return result

    def _wait_for_valid_output(self, path, timeout=4.0):
        parent = ScreenRecorder._wait_for_valid_output
        result, _ = timed(
            f"ScreenRecorder._wait_for_valid_output(path={os.path.basename(path or '')}, timeout={timeout})",
            lambda: parent(self, path, timeout),
        )
        return result

    def stop(self):
        parent_stop = super().stop
        result, elapsed = timed("ScreenRecorder.stop", parent_stop)
        log.warning(f"TOTAL stop() took {elapsed:.3f}s")
        return result


def main():
    log.info(f"python: {sys.executable}")
    log.info(f"record duration: {RECORD_SECONDS}s")

    recorder = TimedScreenRecorder(fps=30)
    log.info(
        f"recorder ready, output_dir={recorder.output_dir}, is_recording={recorder.is_recording}")

    path = recorder.start()
    if not path:
        log.error("start() failed - ffmpeg could not be launched")
        return 1
    log.info(f"recording started -> {path}")

    log.info(f"sleeping {RECORD_SECONDS}s while capturing ...")
    time.sleep(RECORD_SECONDS)
    log.info(
        f"awake after {RECORD_SECONDS}s; is_recording={recorder.is_recording}")

    stopped_path = recorder.stop()
    log.info(f"stop() returned: {stopped_path!r}")

    if stopped_path and os.path.exists(stopped_path):
        size = os.path.getsize(stopped_path)
        log.info(
            f"output file exists, size={size} bytes ({size / 1024 / 1024:.2f} MiB)")
    else:
        log.error("output file is missing after stop()")
        return 1

    # Keep the file so it can be inspected; print its location.
    log.info(f"done. Recording kept at: {stopped_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
