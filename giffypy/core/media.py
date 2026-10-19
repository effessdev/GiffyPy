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

import json
import subprocess

from .constants import FFPROBE


def probe(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,duration,avg_frame_rate:format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
    except json.JSONDecodeError as ex:
        raise ValueError(f"Could not decode media metadata for: {path}") from ex
    streams = j.get("streams") or []
    if not streams:
        raise ValueError(f"No video streams found in {path}")
    st = streams[0]
    dur = 0.0
    for v in (j.get("format", {}).get("duration"), st.get("duration")):
        try:
            dur = float(v)
            break
        except (TypeError, ValueError):
            pass
    try:  # avg_frame_rate is a fraction like "30000/1001"; "0/0" when unknown
        num, den = st.get("avg_frame_rate", "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return int(st["width"]), int(st["height"]), dur, fps
