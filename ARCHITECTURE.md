# Architecture

GiffyPy is a single-window desktop video editor built around two pillars: a Qt GUI (`PySide6`) for interaction and preview, and `ffmpeg`/`ffprobe` as the out-of-process media engine for probing, proxy generation, and export. The Python layer does not own a pixel pipeline; it manages state, timelines, and user intent, and delegates the expensive work to short-lived child processes.

## Tech Stack

- Language: Python 3 (≥ 3.10)
- GUI / event loop: PySide6 (`QtWidgets`, `QtMultimedia`, `QtMultimediaWidgets`)
- Media decoding / playback: `QMediaPlayer` + `QVideoSink` (native Qt playback when the codec allows)
- Media processing: external `ffmpeg` / `ffprobe` binaries launched via `QProcess` or `subprocess`
- Packaging: PyInstaller (`GiffyPy.spec`, `package.bat`), Windows-focused

## Module Layout

```
main.py                       entry point: QApplication, icon, argv file loading
conftest.py                   pytest root config; puts repo root on sys.path

giffypy/
  constants.py                bundled-first ffmpeg/ffprobe discovery and tunables
  media.py                    ffprobe wrapper: probe() -> (width, height, duration, fps)
  loader.py                   MediaLoader: background metadata load and Qt signal bridge
  preview.py                  PreviewManager: proxy generation, scrub painting, frame hiding
  editor.py                   EditorController: playback, splitting, trims, speed edits, undo glue
  export.py                   pure ffmpeg argument builder + numbered export naming
  exporter.py                 ExportController: export lifecycle, progress parsing, save modes
  crop.py                     CropItem + View: crop overlay and bounded navigation viewport
  timeline.py                 Timeline widget: clips, scrub, trim, reorder, pan/zoom painting
  screen_recorder.py          ScreenRecorder: 30 FPS desktop capture wrapper and cursor flag
  session.py                  reset_session(): clears preview state and returns to placeholder UI
  window.py                   Main (QMainWindow): thin orchestration layer, wiring, and state
  ui/
    export_panel.py          export sidebar widgets and start-over confirmation
    toolbar.py                toolbar controls and main window layout
    theme.py                  shared color/theme styling
```

Dependency direction stays acyclic:

```
main.py → window.py → {loader, preview, editor, exporter, crop, timeline, screen_recorder, session} → constants.py
window.py ──> ui/*.py
export.py, media.py ──> no Qt imports
```

`window.py` is intentionally thin: it creates the Qt scene, owns the main state, and delegates editing/export behavior to `EditorController` and `ExportController`. The UI widgets are assembled in `giffypy/ui`, while the real media work remains in the process-free helpers (`media.py`, `preview.py`, `export.py`, `screen_recorder.py`).

## Core Data Model

The edit state is deliberately tiny and non-destructive:

- `s.tl.segs` — a list of `[start, end, speed]` triples in edit order. Each entry is a source-time range plus playback rate. The original file is never modified; splitting, trimming, deleting, and reordering are pure list operations.
- `s.crop.r` — a `QRectF` in source-pixel coordinates, used only when the crop toggle is enabled.
- Export settings — format, FPS step index, resolution scale %, quality 1–100, read from widgets when export runs.
- Undo stack — `s.undo` is a list of `copy.deepcopy(segs)` snapshots. A snapshot is pushed when a `Timeline` gesture commits or when split/delete/undo changes the edit list.

Coordinates are translated between source time and edit time in `timeline.py`. A segment's edit length is `(end - start) / speed`, so clip widths, offsets, and total timeline length all live in edit time. `offset()`, `src()`, `scrub()`, and `head` carry the mapping between the two domains.

## Import & Playback Pipeline

1. **Probe** (`media.py` + `loader.py`): `probe(path)` runs `ffprobe` in a worker thread and returns width, height, duration, and `avg_frame_rate`. `MediaLoader.load()` posts the result back to the main window via Qt signals once the work is complete.
2. **Scene setup** (`window.py`): a `QGraphicsScene` layers three items — `QGraphicsVideoItem` (real decoded output), a `QGraphicsPixmapItem` proxy overlay, and the crop item — inside a `View` that re-fits on resize. When no media is loaded, a centered placeholder widget shows drag-and-drop instructions and buttons for "Open file" and "Record screen".
3. **Screen capture** (`screen_recorder.py`): the placeholder button starts a dedicated `ffmpeg gdigrab` capture process at 30 FPS and offers a keep/discard dialog after stopping. A default-off checkbox toggles the `-draw_mouse` flag before the desktop input, so cursor capture is opt-in. The recorder keeps its live `process` handle until `ffmpeg` has actually exited, so a stop action cannot be re-armed while the shutdown signal is still in flight; that state ordering is essential in the frozen EXE, where the process can linger briefly before the signal is processed. Stopping is non-blocking: `window.py` runs `ScreenRecorder.stop()` (~1 s of ffmpeg finalization plus ffprobe validation) in a Python worker thread and receives the finalized path back on the GUI thread via the `Main.recording_stopped` signal, mirroring the `MediaLoader` pattern; a `recording_stopping` flag and disabled button guard re-entry while the worker is in flight. On shutdown, `Main.closeEvent()` guarantees the capture is finalized: it joins an in-flight stop worker when one exists, otherwise — for a still-capturing recording — it synchronously calls `ScreenRecorder.discard()`, since the async stop/signal path can't complete while the event loop unwinds. `discard()` sends ffmpeg its graceful-shutdown signal and deletes the temp file, so closing the app never orphans a live `ffmpeg` process or leaves an unrecoverable UUID-named capture in the system temp directory.
4. **Proxy generation** (`preview.py`): after a file loads, `PreviewManager.start_preview()` runs a background `QProcess` to emit a low-resolution JPEG sequence (`f%06d.jpg`) into a temp directory, with height capped by `PREVIEW_H` and rate clamped to `min(240, src_fps)` or the fallback `PREVIEW_FPS` value.
5. **Scrub preview** (`PreviewManager.show_preview()`): time → frame index → cached `QPixmap` overlay painted over the video item while paused.
6. **Commit / real frame**: when the user drops a scrub or a trim ends, `player.setPosition()` seeks to the source time. `QVideoSink.videoFrameChanged` hides the proxy overlay when a real frame arrives. If the sink API is unavailable, a short `QTimer` hides the proxy instead.
7. **Codec fallback** (`window.on_error`): if Qt cannot decode the source, a second proxy path transcodes a small H.264 MP4 to a temp file and re-points the `QMediaPlayer` to it so playback still works for codecs Qt cannot open.

Continuous playback does not use the proxy path: a 15 ms `QTimer` mirrors `player.position()` onto the timeline playhead and advances across clip boundaries without forcing a seek when adjacent clips are contiguous in source time. Preview intentionally ignores per-clip speed; the player always runs at source rate. The speed slider is therefore export-only, and the tooltip note warns users that the preview is at source speed while the export uses the clip speed values.

Arrow-key stepping (`Left` / `Right`) is handled by dedicated `QShortcut`s installed in `Main._install_shortcuts()`, so the preview viewport never steals the key events. Each press advances the timeline playhead by one export frame, and the proxy is refreshed without letting the canvas pan or scroll.

## Timeline Widget (`timeline.py`)

The timeline is a fully custom-painted `QWidget` (not a `QGraphicsScene`) with a horizontal `QScrollBar` for pan. Three interaction zones are detected by `hit()`:

- Ruler / empty space → scrub (`preview` signal during drag, `seek` on release)
- Clip body → drag to reorder live in `segs`
- Clip edges (yellow handles) → trim start/end with live proxy preview; the left-edge trim keeps the right edge fixed during the drag and ripples only on release

Edge hit-testing checks the currently selected clip first so adjacent clips sharing a border do not steal the trim grab. Zoom is stored in pixels per second (`z`) in edit time and is anchored to the mouse for `Ctrl+Wheel`; `fit_view()` snapshots a fixed fit zoom and thereafter stays fixed until the user zooms again. Clip widths are edit duration × zoom, so changing a clip's speed changes both its width and the total timeline length.

The timeline emits a small set of signals to the main window and the controller layer:

- `seek(i, t)`: committed position change handled by `Main.on_seek()`.
- `preview(t)`: live scrub proxy preview handled by `Main.show_preview()`.
- `committed(before)`: gesture changed `segs`, used to push an undo snapshot.
- `changed()`: timeline state changed, causing refresh of export labels and buttons.
- `selected(i)`: current clip changed, used to sync the speed slider.

The speed control is implemented in the toolbar layer (`giffypy/ui/toolbar.py`) and synced from `EditorController.sync_speed()`. Its slider is set to a 0.1×–4.0× range, and `on_speed_press()` / `on_speed_release()` capture a before/after state so one undo snapshot is recorded for each drag. The visible note is not a persistent amber banner; the current UI shows the tooltip text on the speed slider while the user drags or hovers it, warning that preview plays at source speed and clip speed affects the export only.

## Cropping (`crop.py`)

`CropItem` is an image-editor-style overlay: the region outside the crop rectangle is dimmed with an even-odd `QPainterPath`, rule-of-thirds guides are drawn inside, and eight handles plus the interior support resize/move operations. Handle size is determined from the view scale so they stay visually constant on screen. Every geometry change invokes the `on_change` callback, which triggers `refresh()` for export-size recalculation. `ExportController.crop_rect()` snaps the crop x/y/w/h to even integers before encoding.

The preview viewport in `crop.py` is a bounded navigable space rather than an unbounded sheet: it starts at a fit-to-frame scale, supports trackpad/wheel panning, `Ctrl+Wheel` zoom, and middle-drag pan, while clamping each move inside a finite navigation rectangle. This makes the crop viewport behave more like a bounded map than an infinite canvas.

## Export Pipeline (`export.py` + `exporter.py`)

`build_ffmpeg_args()` is a pure function that assembles a single `ffmpeg` invocation:

1. Per-segment filter chains: `[0:v]trim=...,setpts=(PTS-STARTPTS)/SPEED[vN]` followed by `concat=n=N:v=1:a=0`. The timeline is represented entirely as a filtergraph; no intermediate files are created in the edit pipeline.
2. Shared post-chain: `crop` (when the crop differs from source size) → `fps` → `scale` with `lanczos`.
3. Format-specific encoding:
   - GIF: palette generation and palette use with Bayer dithering
   - WebP: `libwebp_anim` with lossy quality and loop=0
   - WebM: `libvpx-vp9` with CRF derived from quality
   - MP4 / MOV / MKV: `libx264` + `yuv420p` with CRF derived from quality

`ExportController` owns the runtime lifecycle: it chooses the save mode (`overwrite`, `numbered`, or `saveas`), runs the export in a `QProcess`, parses `-progress pipe:1`, updates the progress bar, writes to a temporary `.__tmp__` file, and swaps it into place with `os.replace()` on success. This also handles the Windows-specific case where overwriting the current source file requires releasing the media player's file handle first. `next_numbered_export_path()` continues to generate names like `name (GiffyPy edit 01)` and scans existing files of the same stem regardless of output extension so GIF/WebP/MP4 copies share a single numbering sequence.

## Process & Threading Model

Everything GUI-related runs on the single Qt event-loop thread. Media work is moved off the GUI thread or run in child processes:

- Background thread — `ffprobe` runs in a worker thread during file load so the window stays responsive while metadata is collected. Screen-recording finalization (`ScreenRecorder.stop()`) runs the same way, returning its result through a Qt signal.
- `QProcess` — proxy JPEG generation, codec-fallback transcoding, and exports all run via `QProcess`, with preview processes explicitly cleared on finish and guarded during shutdown.
- Qt multimedia internals — `QMediaPlayer` decoding happens in native Qt threads; frames arrive through `QVideoSink.videoFrameChanged`.

Temporary artifacts live in the system temp directory (`giffypy_prev_*`, `giffypy_proxy.mp4`, ...). There is no persistent project file; the edit state remains in memory until the user saves a new export.

## Known Constraints & Conventions

- `ffmpeg`/`ffprobe` are resolved once at import in `constants.py`: the bundled copy in `sys._MEIPASS` takes precedence, otherwise a `PATH` search is used.
- The codebase intentionally uses short names (`s`) in methods and some local variables for compactness.
- `QVideoSink` exposes a Python signal called `videoFrameChanged`; older PySide6 variants may present `frameObserved` as the C++ alias. The code guards against both via `getattr`.
- Minimum clip length is `MIN = 0.05 s`; crop handles enforce a 16 px minimum rect.
- Proxy FPS is capped at 240 and falls back to `PREVIEW_FPS` when source FPS is unavailable or the file is VFR/GIF-like.

## Packaging

`package.bat` checks whether `ffmpeg.exe` is on `PATH`; if not, it installs a Gyan FFmpeg package via `winget`, locates the installed binary, and logs an `[INFO]` message before launching PyInstaller. The same pattern is used for Python: if `python` is not on `PATH`, the script installs it, then resolves the executable path so later build steps do not depend on a refreshed shell. Once Python is available, the script upgrades `pip`, installs dependencies from `requirements.txt`, ensures PyInstaller is installed, then invokes the build.

After a successful build, `package.bat` copies `scripts/create_shortcut.bat` into `dist/GiffyPy`, so the shortcut helper ships alongside `GiffyPy.exe`. The spec also copies `ffmpeg.exe` and `ffprobe.exe` into the dist folder as datas so end users do not need a separate ffmpeg installation. `main.py.resource_path()` resolves assets from `sys._MEIPASS` when frozen, and `constants.find_binary()` prefers the bundled binary to the system `PATH`.

`create_shortcut.bat` creates a `.lnk` link in the current user's Start Menu Programs folder using PowerShell and `WScript.Shell`, so the app appears in Windows Search without requiring administrator rights.

`scripts/measure_stop.py` is a development-only diagnostic: it records a 10-second screen capture via `ScreenRecorder` and logs millisecond-precision timings for each step of `stop()` (graceful shutdown, output validation, total), to profile how long stopping a recording takes.
