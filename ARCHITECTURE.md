# Architecture

GiffyPy is a single-window desktop video editor built around two pillars: a **Qt GUI** (`PySide6`) for interaction and preview, and **ffmpeg/ffprobe** as an out-of-process media engine for probing, proxy generation, and export. The Python side holds no pixel pipeline of its own — it manages state, timelines, and user intent, and delegates all heavy media work to short-lived `ffmpeg` child processes.

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 (≥ 3.10) |
| GUI / event loop | PySide6 (`QtWidgets`, `QtMultimedia`, `QtMultimediaWidgets`) |
| Media decoding / playback | `QMediaPlayer` + `QVideoSink` (native Qt playback when the codec allows) |
| Media processing | External `ffmpeg` / `ffprobe` binaries, launched via `QProcess` or `subprocess` |
| Packaging | PyInstaller (`GiffyPy.spec`, `package.bat`), Windows-focused |

## Module Layout

```
main.py                 entry point: QApplication, icon, window creation, argv file loading
giffypy/
  constants.py          ffmpeg/ffprobe PATH discovery, tunables (PREVIEW_FPS, PREVIEW_H, MIN, ...)
  media.py              ffprobe wrapper: probe() -> (width, height, duration, fps)
  crop.py               CropItem (interactive crop rectangle QGraphicsItem) + View (auto-fit QGraphicsView)
  timeline.py           Timeline widget: clip model, scrub/trim/reorder gestures, zoom/pan, painting
  export.py             pure function build_ffmpeg_args(): segments + crop + settings -> ffmpeg CLI args
  window.py             Main (QMainWindow): orchestrates everything — loading, preview, playback, undo, export
```

Dependency direction is strictly acyclic:

```
main.py → window.py → {media, export, crop, timeline} → constants.py
```

`export.py` and `media.py` are side-effect-free builders/wrappers with no Qt imports; all Qt widgets live in `crop.py`, `timeline.py`, and `window.py`. `window.py` is the only module that wires signals between components.

## Core Data Model

The edit state is deliberately tiny and non-destructive:

- **`s.tl.segs`** — a list of `[start, end]` source-time pairs in *edit order*. This is the entire edit; the original file is never modified. Splitting, trimming, deleting, and reordering are pure list operations.
- **`s.crop.r`** — a `QRectF` in source-pixel coordinates (only meaningful when the crop toggle is on).
- **Export settings** — format, FPS step index, resolution scale %, quality 1–100, read live from widgets at export time.
- **Undo stack** — `s.undo` is a list of `copy.deepcopy(segs)` snapshots. A snapshot is pushed when a `Timeline` gesture *commits* (mouse release with an actual change) or on split/delete/undo. Undo simply pops and restores.

Coordinates come in two flavors and the `Timeline` translates between them constantly: **source time** (a position in the original file) and **edit time** (position in the concatenated output). `offset()`, `src()`, `scrub()`, and `head` handle the mapping.

## Import & Playback Pipeline

1. **Probe** (`media.py`): `load(path)` runs ffprobe synchronously for dimensions, duration, and `avg_frame_rate` (fraction parsing, with fallbacks).
2. **Scene setup** (`window.py`): a `QGraphicsScene` layers three items — `QGraphicsVideoItem` (z=0, real decoder output), a `QGraphicsPixmapItem` proxy overlay (z=0.5), and the `CropItem` (z=1) — inside a `View` that re-fits on resize.
3. **Proxy sequence** (`window.start_preview`): immediately on load, a background `QProcess` runs ffmpeg to emit a low-resolution JPEG sequence (`f%06d.jpg`, height ≤ `PREVIEW_H`) at the *source frame rate* (1:1 frame mapping) into a fresh temp dir. Scrubbing is then an O(1) file read instead of a video seek — this is what makes scrubbing feel instant.
4. **Scrub preview** (`window.show_preview`): time → frame index → cached `QPixmap` (LRU-ish dict, cleared past 120 entries) painted over the video item while paused.
5. **Commit / real frame**: on gesture release, a true `QMediaPlayer.setPosition()` seek runs; `QVideoSink.videoFrameChanged` fires `on_real_frame`, which hides the proxy overlay so the full-resolution decoded frame shows. If the sink API is unavailable, a 300 ms timer hides the proxy instead.
6. **Codec fallback** (`window.on_error`): if Qt's backend cannot decode the file, a *second* proxy strategy kicks in — ffmpeg transcodes a light 720p H.264 MP4 into the temp dir and the player re-points at it, giving native playback for codecs Qt can't open.

Continuous playback doesn't use proxies: a 15 ms `QTimer` (`tick`) mirrors `player.position()` onto the timeline playhead and advances across clip boundaries, skipping the seek entirely when adjacent clips are contiguous in the source.

## Timeline Widget (`timeline.py`)

A fully custom-painted `QWidget` (no QGraphicsScene) with a horizontal `QScrollBar` for pan. Three interaction zones resolved by `hit()`:

- **Ruler / empty space** → scrub (`preview` signal during drag for proxy-only updates; `seek` on release).
- **Clip body** → drag to reorder (live re-insertion into `segs` while dragging).
- **Clip edges** (yellow handles) → trim start/end with live proxy preview; left-edge trims "shift in place" during drag and ripple on release.

Edge hit-testing checks the *selected* clip first so adjacent clips sharing a border don't steal the grab. Zoom is pixels-per-second (`z`), anchored at the mouse for `Ctrl+Wheel`; `fit_view()` snapshots a fixed fit zoom and nothing auto-refits afterward.

State-change protocol to `Main` via four signals:

| Signal | Meaning | Main's reaction |
|---|---|---|
| `seek(i, t)` | committed position change | move player, show real frame |
| `preview(t)` | live scrub, proxy frame only | paint proxy, no seek |
| `committed(before)` | gesture changed `segs` | push snapshot for undo |
| `changed()` | anything visible changed | refresh export panel labels/buttons |

## Cropping (`crop.py`)

`CropItem` is an image-editor-style overlay: the region *outside* the crop rect is dimmed via an even-odd `QPainterPath`, rule-of-thirds guides are drawn inside, and eight handles plus the interior support resize/move. Handles are sized by dividing by the view's scale factor so they stay a constant 7 px on screen regardless of zoom. Every geometry change invokes the `on_change` callback (wired to `Main.refresh`), which recomputes the output-size preview. `Main.crop_rect()` snaps crop x/y/w/h to even integers (required by encoders working in YUV 4:2:0).

## Export Pipeline (`export.py` + `window.py`)

`build_ffmpeg_args()` is a pure function that assembles a single `ffmpeg` invocation:

1. **Per-segment** `[0:v]trim=...,setpts=PTS-STARTPTS[vN]` chains, then `concat=n=N:v=1:a=0` — the timeline is expressed entirely as a filtergraph; no intermediate files.
2. **Shared post-chain**: `crop` (only if the rect differs from source size) → `fps` → `scale` with lanczos.
3. **Format-specific encoding**:
   - **GIF**: quality maps to palette color count (16–256); `split` + `palettegen=stats_mode=diff` + `paletteuse` with Bayer dithering in one filtergraph.
   - **WebP**: `libwebp_anim`, lossy, quality passed through.
   - **WebM**: `libvpx-vp9` with CRF inverted from quality.
   - **MP4/MOV/MKV**: `libx264` + `yuv420p`, CRF inverted from quality.

`window.py` handles the lifecycle: exports run in a `QProcess` with `-progress pipe:1`, parsing `out_time_us` lines to drive the progress bar. Output is always written to a `.__tmp__` file and `os.replace`d into place on success (atomic-ish, and survives mid-export failure). Four save modes (`overwrite` with confirmation, `numbered` copy, `saveas` dialog, `copy to clipboard` via temp file + `QImage` → clipboard, GIF/WebP only) share this machinery through a `clip_mode` flag. A `busy` flag disables export buttons during a run. Overwriting the source file first releases the player's file handle (`setSource(QUrl())`), a Windows-specific necessity.

## Process & Threading Model

Everything GUI-related runs on the single Qt event-loop thread. All media work is out-of-process:

- **`subprocess.run`** — one synchronous ffprobe call at load time (fast enough to block on).
- **`QProcess`** — proxy JPEG generation (killable, replaced per-load), codec-fallback transcoding, and exports (progress parsed from stdout).
- **Qt multimedia internals** — `QMediaPlayer` decoding happens in native Qt threads; frames arrive via the `videoFrameChanged` signal.

Temp artifacts live in the system temp dir: `giffypy_prev_*` (JPEG proxy dirs, old ones cleaned via delayed `QTimer.singleShot` and on close), `giffypy_proxy.mp4` (codec fallback), `giffypy_clip_*` (clipboard exports). There is no persistent project file; state is in-memory only.

## Known Constraints & Conventions

- ffmpeg/ffprobe must be on `PATH`; discovered once at import in `constants.py`, with a startup warning in the status label if missing.
- The codebase uses single-letter parameter/self names (`s`) as a deliberate compactness convention.
- `QVideoSink`'s Python signal is `videoFrameChanged` (`frameObserved` is the C++ alias); connecting the wrong name fails silently, so it's accessed via `getattr` with a `try` guard for older PySide6.
- Minimum clip length is `MIN = 0.05 s`; crop handles enforce a 16 px minimum rect.
- Proxy FPS is capped at 240 and falls back to `PREVIEW_FPS` (12) when the source rate can't be probed (some GIFs / VFR files).

## Packaging

`package.bat` runs PyInstaller in `--onedir --windowed` mode with `icon.ico` bundled as data; `main.py.resource_path` resolves assets from `sys._MEIPASS` when frozen. The frozen app still requires ffmpeg on the user's `PATH` (it is not bundled).
