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
import re


EXT_MAP = {
    "WebP": ".webp",
    "GIF": ".gif",
    "MP4": ".mp4",
    "WebM": ".webm",
    "MOV": ".mov",
    "MKV": ".mkv",
}


def next_numbered_export_path(path, ext):
    """Return the next numbered export path for a source file.

    Example: "clip.mp4" -> "clip (GiffyPy edit 01).gif".
    Numbering ignores extension and starts from 01, so a GIF export will not
    collide with an existing MP4 copy and vice versa.
    """
    folder, filename = os.path.split(path)
    stem, _ = os.path.splitext(filename)
    pattern = re.compile(
        rf"^{re.escape(stem)} \(GiffyPy edit (\d+)\)(?:\.[^.]+)?$")
    used = set()

    if os.path.isdir(folder):
        for entry in os.scandir(folder):
            if entry.is_file():
                match = pattern.match(entry.name)
                if match:
                    used.add(int(match.group(1)))

    n = 1
    while n in used:
        n += 1
    return os.path.join(folder, f"{stem} (GiffyPy edit {n:02d}){ext}")


def build_ffmpeg_args(src, dst, fmt, segs, crop, src_size, out_size, fps, q):
    """Build the ffmpeg argument list for exporting `segs` of `src` into `dst`.

    crop = (x, y, w, h); src_size = (W, H); out_size = (W, H); q = quality 1..100
    """
    x, y, w, h = crop
    W, H = out_size
    parts = []
    for i, (b, e, sp) in enumerate(segs):
        st = "PTS-STARTPTS" if abs(sp -
                                   1.0) < 1e-9 else f"(PTS-STARTPTS)/{sp:.9g}"
        parts.append(f"[0:v]trim=start={b:.4f}:end={e:.4f},setpts={st}[v{i}]")
    vf = ([f"crop={w}:{h}:{x}:{y}"] if (w, h) != tuple(src_size)
          else []) + [f"fps={fps}", f"scale={W}:{H}:flags=lanczos"]
    fc = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(
        len(segs))) + f"concat=n={len(segs)}:v=1:a=0,{','.join(vf)}"
    if fmt == "GIF":
        colors = 16 + q * 240 // 100
        fc += f"[o];[o]split[a][b];[a]palettegen=max_colors={colors}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle[out]"
        enc = ["-loop", "0"]
    elif fmt == "WebP":
        fc += "[out]"
        enc = ["-c:v", "libwebp_anim", "-lossless", "0", "-q:v",
               str(q), "-compression_level", "4", "-loop", "0"]
    elif fmt == "WebM":
        fc += "[out]"
        crf = int(63 - q * 48 / 100)
        enc = ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0"]
    else:  # MP4, MOV, MKV
        fc += "[out]"
        crf = int(51 - q * 33 / 100)
        enc = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf)]
    return ["-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats", "-i", src,
            "-filter_complex", fc, "-map", "[out]", "-an", *enc, dst]
