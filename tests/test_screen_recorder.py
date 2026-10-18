import pytest

from giffypy.media import probe
from giffypy.screen_recorder import ScreenRecorder


def test_screen_recorder_build_command_uses_desktop_capture_at_30fps(monkeypatch):
    monkeypatch.setattr("giffypy.screen_recorder.FFMPEG", "ffmpeg")

    cmd = ScreenRecorder.build_command(r"C:\\tmp\\recording.mp4", fps=30)

    assert cmd[:5] == ["ffmpeg", "-y", "-f", "gdigrab", "-framerate"]
    assert "desktop" in cmd
    assert cmd[cmd.index("-pix_fmt"):cmd.index("-pix_fmt") + 2] == ["-pix_fmt", "yuv420p"]
    assert cmd[-1].endswith("recording.mp4")


def test_probe_raises_clear_error_when_no_video_streams(monkeypatch):
    monkeypatch.setattr("giffypy.media.FFPROBE", "ffprobe")

    class DummyResult:
        stdout = '{"format": {}}'

    monkeypatch.setattr("giffypy.media.subprocess.run", lambda *args, **kwargs: DummyResult())

    with pytest.raises(ValueError, match="No video streams found"):
        probe("C:/tmp/bad.mp4")
