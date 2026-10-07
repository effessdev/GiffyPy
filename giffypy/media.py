import json
import subprocess

from .constants import FFPROBE


def probe(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,duration,avg_frame_rate:format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout)
    st = j["streams"][0]
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
