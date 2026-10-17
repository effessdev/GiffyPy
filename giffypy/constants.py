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

import shutil

FFMPEG, FFPROBE = shutil.which("ffmpeg"), shutil.which("ffprobe")
FPS_STEPS = [0.5, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 50, 60]
# low-res image sequence for instant scrub preview; PREVIEW_FPS is the fallback seq rate
# used only when the source frame rate can't be probed (some GIFs / VFR files)
PREVIEW_FPS, PREVIEW_H = 12, 480
MIN = 0.05  # minimum clip length (s)
FILTER = ("Video (*.mp4 *.mkv *.mov *.webm *.avi *.flv *.ts *.m2ts *.m4v *.wmv *.mpg *.mpeg *.ogv *.3gp *.gif);;All files (*)")
CLIP_FMTS = {"GIF", "WebP"}  # image-based formats that can go on the clipboard
