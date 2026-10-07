import shutil

FFMPEG, FFPROBE = shutil.which("ffmpeg"), shutil.which("ffprobe")
FPS_STEPS = [0.5, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 50, 60]
# low-res image sequence for instant scrub preview; PREVIEW_FPS is the fallback seq rate
# used only when the source frame rate can't be probed (some GIFs / VFR files)
PREVIEW_FPS, PREVIEW_H = 12, 480
MIN = 0.05  # minimum clip length (s)
FILTER = ("Video (*.mp4 *.mkv *.mov *.webm *.avi *.flv *.ts *.m2ts *.m4v *.wmv *.mpg *.mpeg *.ogv *.3gp *.gif);;All files (*)")
CLIP_FMTS = {"GIF", "WebP"}  # image-based formats that can go on the clipboard
