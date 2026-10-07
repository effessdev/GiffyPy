EXT_MAP = {
    "WebP": ".webp",
    "GIF": ".gif",
    "MP4": ".mp4",
    "WebM": ".webm",
    "MOV": ".mov",
    "MKV": ".mkv",
}


def build_ffmpeg_args(src, dst, fmt, segs, crop, src_size, out_size, fps, q):
    """Build the ffmpeg argument list for exporting `segs` of `src` into `dst`.

    crop = (x, y, w, h); src_size = (W, H); out_size = (W, H); q = quality 1..100
    """
    x, y, w, h = crop
    W, H = out_size
    parts = [
        f"[0:v]trim=start={b:.4f}:end={e:.4f},setpts=PTS-STARTPTS[v{i}]" for i, (b, e) in enumerate(segs)]
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
