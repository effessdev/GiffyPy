import pytest

from giffypy.media import probe
from giffypy.screen_recorder import ScreenRecorder


def test_screen_recorder_build_command_uses_desktop_capture_at_30fps(monkeypatch):
    monkeypatch.setattr("giffypy.screen_recorder.FFMPEG", "ffmpeg")

    cmd = ScreenRecorder.build_command(r"C:\\tmp\\recording.mp4", fps=30)

    assert cmd[:5] == ["ffmpeg", "-y", "-f", "gdigrab", "-framerate"]
    assert "desktop" in cmd
    assert cmd[cmd.index("-framerate") + 2:cmd.index("desktop") + 1] == ["-draw_mouse", "0", "-i", "desktop"]
    assert cmd[cmd.index("-pix_fmt"):cmd.index("-pix_fmt") + 2] == ["-pix_fmt", "yuv420p"]
    assert cmd[-1].endswith("recording.mp4")


def test_screen_recorder_build_command_can_enable_cursor_capture(monkeypatch):
    monkeypatch.setattr("giffypy.screen_recorder.FFMPEG", "ffmpeg")

    cmd = ScreenRecorder.build_command(r"C:\\tmp\\recording.mp4", fps=30, capture_cursor=True)

    assert cmd[cmd.index("-framerate") + 2:cmd.index("desktop") + 1] == ["-draw_mouse", "1", "-i", "desktop"]


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
    monkeypatch.setattr(recorder, "_wait_for_valid_output", lambda *args, **kwargs: True)

    assert recorder.stop() == "C:/tmp/recording.mp4"
    assert recorder.process is None
    assert recorder.output_path is None


def test_screen_recorder_stop_keeps_state_while_signal_is_in_flight(monkeypatch):
    class DummyProcess:
        def __init__(self, recorder):
            self.recorder = recorder

        def poll(self):
            return None

        def send_signal(self, *_):
            assert self.recorder.process is self

        def wait(self, timeout=None):
            assert self.recorder.process is self
            return None

    recorder = ScreenRecorder()
    proc = DummyProcess(recorder)
    recorder.process = proc
    recorder.output_path = "C:/tmp/recording.mp4"
    monkeypatch.setattr(recorder, "_wait_for_valid_output", lambda *args, **kwargs: True)

    assert recorder.stop() == "C:/tmp/recording.mp4"
    assert recorder.process is None
    assert recorder.output_path is None


def test_screen_recorder_stop_falls_back_to_terminate_when_console_signal_is_unsupported(monkeypatch):
    class DummyProcess:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def send_signal(self, *_):
            raise OSError("console signal not available")

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return None

    recorder = ScreenRecorder()
    proc = DummyProcess()
    recorder.process = proc
    recorder.output_path = "C:/tmp/recording.mp4"
    monkeypatch.setattr(recorder, "_wait_for_valid_output", lambda *args, **kwargs: True)

    assert recorder.stop() == "C:/tmp/recording.mp4"
    assert proc.terminated is True
    assert recorder.process is None
    assert recorder.output_path is None


def test_screen_recorder_stop_retries_until_probe_sees_a_valid_stream(monkeypatch, tmp_path):
    path = tmp_path / "recording.mp4"
    path.write_bytes(b"not empty yet")
    calls = {"count": 0}

    class DummyProcess:
        def poll(self):
            return None

        def send_signal(self, *_):
            pass

        def wait(self, timeout=None):
            return None

    def fake_probe(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] < 2:
            raise ValueError("No video streams found")
        return 1280, 720, 3.0, 30.0

    monkeypatch.setattr("giffypy.media.probe", fake_probe)

    recorder = ScreenRecorder()
    recorder.process = DummyProcess()
    recorder.output_path = str(path)

    assert recorder.stop() == str(path)


def test_probe_raises_clear_error_when_no_video_streams(monkeypatch):
    monkeypatch.setattr("giffypy.media.FFPROBE", "ffprobe")

    class DummyResult:
        stdout = '{"format": {}}'

    monkeypatch.setattr("giffypy.media.subprocess.run", lambda *args, **kwargs: DummyResult())

    with pytest.raises(ValueError, match="No video streams found"):
        probe("C:/tmp/bad.mp4")
