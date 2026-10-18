import pytest

from giffypy.media import probe
from giffypy.screen_recorder import ScreenRecorder


class DummyPipe:
    """Stand-in for Popen(..., stdin=PIPE).stdin."""

    def __init__(self, fail_write=False, on_write=None, on_wait_check=None):
        self.closed = False
        self.written = b""
        self._fail_write = fail_write
        self._on_write = on_write

    def write(self, data):
        if self._fail_write:
            raise BrokenPipeError("pipe closed")
        if self._on_write:
            self._on_write()
        self.written += data

    def flush(self):
        pass

    def close(self):
        self.closed = True


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
        def __init__(self):
            self.stdin = DummyPipe()

        def poll(self):
            return None

        def wait(self, timeout=None):
            return None

    recorder = ScreenRecorder()
    recorder.process = DummyProcess()
    recorder.output_path = "C:/tmp/recording.mp4"
    monkeypatch.setattr(recorder, "_wait_for_valid_output", lambda *args, **kwargs: True)

    assert recorder.stop() == "C:/tmp/recording.mp4"
    assert recorder.process is None
    assert recorder.output_path is None


def test_screen_recorder_stop_sends_graceful_quit_before_clearing_state(monkeypatch):
    """stop() should write 'q' to stdin (so ffmpeg finalizes the mp4) and
    must not clear recorder.process/output_path until the process has
    actually exited."""

    class DummyProcess:
        def __init__(self, recorder):
            self.recorder = recorder
            self.stdin = DummyPipe(on_write=self._assert_state_intact)

        def _assert_state_intact(self):
            assert self.recorder.process is self

        def poll(self):
            return None

        def wait(self, timeout=None):
            assert self.recorder.process is self
            return None

    recorder = ScreenRecorder()
    proc = DummyProcess(recorder)
    recorder.process = proc
    recorder.output_path = "C:/tmp/recording.mp4"
    monkeypatch.setattr(recorder, "_wait_for_valid_output", lambda *args, **kwargs: True)

    assert recorder.stop() == "C:/tmp/recording.mp4"
    assert proc.stdin.written == b"q"
    assert recorder.process is None
    assert recorder.output_path is None


def test_screen_recorder_stop_falls_back_to_signal_when_stdin_write_fails(monkeypatch):
    class DummyProcess:
        def __init__(self):
            self.stdin = DummyPipe(fail_write=True)
            self.signaled = False

        def poll(self):
            return None

        def send_signal(self, *_):
            self.signaled = True

        def wait(self, timeout=None):
            return None

    recorder = ScreenRecorder()
    proc = DummyProcess()
    recorder.process = proc
    recorder.output_path = "C:/tmp/recording.mp4"
    monkeypatch.setattr(recorder, "_wait_for_valid_output", lambda *args, **kwargs: True)

    assert recorder.stop() == "C:/tmp/recording.mp4"
    assert proc.signaled is True
    assert recorder.process is None
    assert recorder.output_path is None


def test_screen_recorder_stop_falls_back_to_terminate_when_graceful_shutdown_fails(monkeypatch):
    class DummyProcess:
        def __init__(self):
            self.stdin = DummyPipe(fail_write=True)
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
        def __init__(self):
            self.stdin = DummyPipe()

        def poll(self):
            return None

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


def test_screen_recorder_discard_stops_process_before_removing_file(tmp_path):
    """discard() must stop ffmpeg first: on Windows the file is still
    locked while ffmpeg holds it open, and deleting out from under a live
    process also leaks an orphaned ffmpeg."""

    path = tmp_path / "recording.mp4"
    path.write_bytes(b"partial")

    class DummyProcess:
        def __init__(self):
            self.stdin = DummyPipe()
            self.exited = False

        def poll(self):
            return None if not self.exited else 0

        def wait(self, timeout=None):
            self.exited = True
            return None

    recorder = ScreenRecorder()
    proc = DummyProcess()
    recorder.process = proc
    recorder.output_path = str(path)

    result = recorder.discard()

    assert result == str(path)
    assert proc.stdin.written == b"q"
    assert not path.exists()
    assert recorder.process is None
    assert recorder.output_path is None


def test_screen_recorder_discard_removes_file_when_not_recording(tmp_path):
    path = tmp_path / "recording.mp4"
    path.write_bytes(b"done")

    recorder = ScreenRecorder()
    recorder.output_path = str(path)
    recorder.process = None

    assert recorder.discard() == str(path)
    assert not path.exists()


def test_probe_raises_clear_error_when_no_video_streams(monkeypatch):
    monkeypatch.setattr("giffypy.media.FFPROBE", "ffprobe")

    class DummyResult:
        stdout = '{"format": {}}'

    monkeypatch.setattr("giffypy.media.subprocess.run", lambda *args, **kwargs: DummyResult())

    with pytest.raises(ValueError, match="No video streams found"):
        probe("C:/tmp/bad.mp4")
