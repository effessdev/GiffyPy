from giffypy.export import next_numbered_export_path


def test_next_numbered_export_path_starts_at_01_and_ignores_extension(tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"source")

    assert next_numbered_export_path(str(src), ".gif") == str(
        tmp_path / "clip (GiffyPy edit 01).gif"
    )

    (tmp_path / "clip (GiffyPy edit 01).mp4").write_bytes(b"one")
    (tmp_path / "clip (GiffyPy edit 02).webm").write_bytes(b"two")

    assert next_numbered_export_path(str(src), ".gif") == str(
        tmp_path / "clip (GiffyPy edit 03).gif"
    )
