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


def test_screen_recorder_start_rejects_immediate_failure(monkeypatch):
    monkeypatch.setattr("giffypy.screen_recorder.FFMPEG", "ffmpeg")

    class DummyProcess:
        def poll(self):
            return 1

    monkeypatch.setattr("giffypy.screen_recorder.subprocess.Popen", lambda *args, **kwargs: DummyProcess())

    recorder = ScreenRecorder()

    assert recorder.start() is None
    assert recorder.output_path is None
    assert recorder.process is None


def test_screen_recorder_stop_clears_state_on_success(monkeypatch):
    class DummyProcess:
        def poll(self):
            return None

        def send_signal(self, *_):
            pass

        def wait(self, timeout=None):
            return None

    recorder = ScreenRecorder()
    recorder.process = DummyProcess()
    recorder.output_path = "C:/tmp/recording.mp4"

    assert recorder.stop() == "C:/tmp/recording.mp4"
    assert recorder.process is None
    assert recorder.output_path is None


def test_probe_raises_clear_error_when_no_video_streams(monkeypatch):
    monkeypatch.setattr("giffypy.media.FFPROBE", "ffprobe")

    class DummyResult:
        stdout = '{"format": {}}'

    monkeypatch.setattr("giffypy.media.subprocess.run", lambda *args, **kwargs: DummyResult())

    with pytest.raises(ValueError, match="No video streams found"):
        probe("C:/tmp/bad.mp4")
