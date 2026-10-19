# Architecture

GiffyPy is a single-window desktop video editor. PySide6 handles all UI and
event flow; ffmpeg/ffprobe do the heavy media work in short-lived child
processes. The Python layer owns only state and intent — never a pixel
pipeline.

## Tech Stack

- Python 3 (≥ 3.10), PySide6 (`QtWidgets`, `QtMultimedia`, `QtMultimediaWidgets`)
- External `ffmpeg` / `ffprobe` via `QProcess` / `subprocess`
- PyInstaller packaging (`GiffyPy.spec`, `build.bat`), Windows-focused

## Module Layout

```
main.py         entry point: QApplication, icon, argv file loading
giffypy/
  window.py     Main (QMainWindow): the only module that wires the others together
  core/         logic, no widget rendering
    constants.py        bundled-first ffmpeg/ffprobe discovery and tunables
    media.py            ffprobe wrapper: probe() -> (width, height, duration, fps)
    loader.py           MediaLoader: background metadata load and Qt signal bridge
    preview.py          PreviewManager: proxy sequence generation and scrub painting
    editor.py           EditorController: playback, split, trim, speed, undo glue
    export.py           pure ffmpeg argument builder + numbered export naming
    exporter.py         ExportController: export lifecycle, progress, save modes
    screen_recorder.py  ScreenRecorder: gdigrab desktop capture wrapper
    session.py          reset_session(): back to a clean placeholder state
  ui/           everything that renders or takes mouse/key input
    timeline.py         custom-painted timeline: clips, scrub, trim, reorder, zoom
    crop.py            CropItem overlay + View bounded navigation viewport
    export_panel.py    export sidebar widgets
    toolbar.py         toolbar controls and main window layout
    theme.py           shared color/theme styling
```

Dependencies stay acyclic; only `window.py` crosses layers:

```
main.py → window.py → {core/*, ui/*} → core/constants.py
core/export.py, core/media.py have no Qt imports
```

## Core Concepts

- **Non-destructive edits.** The whole edit is `s.tl.segs`: a list of
  `[start, end, speed]` triples in edit order over the untouched source file.
  Split/trim/delete/reorder are pure list operations. Undo is a stack of
  `deepcopy(segs)` snapshots. `s.crop.r` is a `QRectF` in source pixels.
- **Two time domains.** Source time vs edit time; a segment's edit length is
  `(end - start) / speed`. `ui/timeline.py` owns the translation.
- **Instant preview via temporary image sequence.** While paused/scrubbing, we
  never decode the real video. On load, `core/preview.py` spawns ffmpeg to
  dump a low-res JPEG sequence (`f%06d.jpg`) into a temp dir; moving the
  playhead is just an index lookup + `QPixmap` blit over the video item, so
  scrubbing updates immediately even for heavy codecs. When the user commits a
  position, the real player seeks and `QVideoSink` hides the overlay. Playback
  itself uses `QMediaPlayer` at source speed (per-clip speed is export-only).
- **Everything as a filtergraph.** Export builds one ffmpeg command
  (`core/export.py`): per-segment `trim`+`setpts` → `concat` → `crop`/`fps`/
  `scale` → format encoder. No intermediate files in the edit pipeline.
  `core/exporter.py` runs it, parses `-progress pipe:1`, and swaps a
  `.__tmp__` file into place on success.
- **Threading.** One Qt thread for UI; ffprobe on load and recording stop run
  in worker threads; proxy generation, codec fallback, and export run as
  `QProcess` children. Temp artifacts live in the system temp dir; there is no
  project file.

## Look Here For

| Topic | Where |
|---|---|
| ffmpeg binary resolution, tunables (`PREVIEW_H`, `MIN`, FPS steps) | `core/constants.py` |
| Gesture zones, hit-testing, zoom | `ui/timeline.py` |
| Crop overlay handles, bounded pan/zoom viewport | `ui/crop.py` |
| Speed slider UI + undo-on-drag | `ui/toolbar.py`, `core/editor.py` |
| Save modes, GIF/WebP/WebM/MP4 encoding args | `core/export.py`, `core/exporter.py` |
| Recording cap (`-t 600`), cursor flag, shutdown cleanup | `core/screen_recorder.py`, `window.closeEvent` |
| Codec fallback transcode | `window.on_error` |

## Conventions

- Short names (`s`) in methods/locals are intentional, for compactness.
- `QVideoSink` signal is `videoFrameChanged`; code guards the old
  `frameObserved` alias via `getattr`.
- Min clip length `0.05 s`; crop snaps to even pixels (YUV-friendly).

## Packaging

`build.bat` ensures Python, ffmpeg, and PyInstaller are available (winget
installs if missing), builds via `GiffyPy.spec`, and ships `ffmpeg.exe` /
`ffprobe.exe` and `create_shortcut.bat` inside `dist/GiffyPy`. Bundled
binaries take precedence over `PATH` at runtime (`core/constants.py`).

`scripts/measure_stop.py` is a dev-only diagnostic profiling how long stopping
a recording takes.
